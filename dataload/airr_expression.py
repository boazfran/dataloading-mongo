# Script for loading MIXCR formatted annotation file 
# into an iReceptor data node MongoDb database

import sys
import os.path
import pandas as pd
import numpy as np 
import json
import gzip
import time

from expression import Expression
from annotation import Annotation
from parser import Parser

class AIRR_Expression(Expression):
    
    def __init__( self, verbose, repository_tag, repository_chunk, airr_map, repository):
        Expression.__init__(self, verbose, repository_tag, repository_chunk, airr_map, repository)
        # The annotation tool used for the AIRR-Expression is ambiguous, use a generic name.
        self.setAnnotationTool("AIRR-Expression")
        # The default column in the AIRR Mapping file is "airr" as this is parsing AIRR
        # fields.. This can be overrideen by the user should they choose to use a
        # differnt set of columns from the file.
        self.setFileMapping("airr")

    def process(self, filewithpath):

        # This reads one AIRR Expression JSON file at a time, given the full file (path) name
        # May also be gzip compressed file
        
        # Open, decompress then read(), if it is a gz archive
        success = True

        # Check to see if the file exists and return if not.
        if not os.path.isfile(filewithpath):
            print("ERROR: Could not open AIRR Expression file ", filewithpath)
            return False

        # Get root filename from the path, should be a file if the path is file,
        # so not checking again 8-)
        filename = os.path.basename(filewithpath)

        if filewithpath.endswith(".gz"):
            if self.verbose():
                print("Info: Reading data gzip archive: "+filewithpath)
            with gzip.open(filewithpath, 'rb') as file_handle:
                # read file directly from the file handle 
                # (Pandas read_csv call handles this...)
                success = self.processAIRRExpressionFile(file_handle, filename)

        else: # read directly as a regular text file
            if self.verbose():
                print("Info: Reading text file: "+filewithpath)
            file_handle = open(filewithpath, "r")
            success = self.processAIRRExpressionFile(file_handle, filename)

        return success

    def processAIRRExpressionFile( self, file_handle, filename ):

        # Start a timer for performance reasons.
        t_start_full = time.perf_counter()

        # Get the AIRR Map object for this class (for convenience).
        airr_map = self.getAIRRMap()

        # Set the tag for the repository that we are using.
        repository_tag = self.getRepositoryTag()
        # Get the tag to use for iReceptor specific mappings
        ireceptor_tag = self.getiReceptorTag()
        # Set the tag for the AIRR column
        airr_tag = self.getAIRRTag()

        # Get the fields to use for finding repertoire IDs, either using those IDs
        # directly or by looking for a repertoire ID based on a rearrangement file
        # name.
        repertoire_link_field = self.getRepertoireLinkIDField()
        expression_link_field = self.getAnnotationLinkIDField()
        rep_expression_link_field = airr_map.getMapping(
                                         expression_link_field,
                                         ireceptor_tag, repository_tag)
        if rep_expression_link_field is None:
            print("ERROR: Could not get repertoire link field from AIRR mapping.")
            return False

        # Set the tag for the file mapping that we are using. Ths is essentially the
        # look up into the columns of the AIRR Mapping that we are using. 
        filemap_tag = self.getFileMapping()

        # Define the number of records to iterate over
        chunk_size = self.getRepositoryChunkSize()

        # Get the single, unique repertoire link id for the filename we are loading. If
        # we can't find one, this is an error and we return failure.
        repertoire_link_id = self.getRepertoireInfo(filename)
        if repertoire_link_id is None:
            print("ERROR: Could not link file %s to a valid repertoire"%(filename))
            return False

        # Get the column of values from the AIRR tag. We only want the
        # Expression related fields.
        map_column = self.getAIRRMap().getExpressionMapColumn(airr_tag)
        # Get a boolean column that flags columns of interest. Exclude nulls.
        fields_of_interest = map_column.notnull()
        # Afer the following airr_fields contains N columns (e.g. iReceptor, AIRR)
        # that contain the AIRR Repertoire mappings.
        airr_fields = self.getAIRRMap().getExpressionRows(fields_of_interest)

        # Extract the fields that are of interest for this file. Essentially all non
        # null fields in the file. This is a boolean array that is T everywhere there
        # is a notnull field in the column of interest.
        map_column = airr_map.getExpressionMapColumn(filemap_tag)
        fields_of_interest = map_column.notnull()

        # We select the rows in the mapping that contain fields of interest for Expression.
        # At this point, file_fields contains N columns that contain our mappings for
        # the specific formats (e.g. airr). The rows are limited to 
        # only data that is relevant to Expression
        file_fields = airr_map.getExpressionRows(fields_of_interest)

        # We need to build the set of fields that the repository can store. We don't
        # want to extract fields that the repository doesn't want.
        expressionColumns = []
        columnMapping = {}
        if self.verbose():
            print("Info: Dumping expected %s (%s) to repository mapping"
                  %(self.getAnnotationTool(),filemap_tag))
        for index, row in file_fields.iterrows():
            if self.verbose():
                print("Info:    %s -> %s"
                      %(str(row[filemap_tag]), str(row[repository_tag])))
            # If the repository column has a value for the Expression field, track the field
            # from both the Expression and repository side.
            if not pd.isnull(row[repository_tag]):
                expressionColumns.append(row[filemap_tag])
                columnMapping[row[filemap_tag]] = row[repository_tag]
            else:
                if self.verbose():
                    print("Info:    Repository does not support " +
                          str(row[filemap_tag]) + ", not inserting into repository")

        # Load in the JSON file. The file should be an array of expression objects as
        # per the AIRR spec.
        if self.verbose():
            print("Info: Reading the Expression JSON array", flush=True)
        expression_array = json.load(file_handle)
        expression_records = len(expression_array)
        if self.verbose():
            print("Info: Read %d Expression objects"%(expression_records), flush=True)

        # Get the fields to use for the created and updated dates
        ir_created_at = airr_map.getMapping("ir_created_at_expression", 
                                            ireceptor_tag, repository_tag,
                                            airr_map.getIRExpressionClass())
        ir_updated_at = airr_map.getMapping("ir_updated_at_expression",
                                            ireceptor_tag, repository_tag,
                                            airr_map.getIRExpressionClass())

        t_preamble_end = time.perf_counter()
        print("Info: Preamble time = %fs"% (t_preamble_end-t_start_full),flush=True)
        print("Info: Processing %d records"% (chunk_size),flush=True)

        # Iterate over each element in the array 
        total_records = 0
        block_count = 0
        block_array = []
        # Timing stuff
        t_start = time.perf_counter()
        # Left in timing code (commented out) in case we want to go back and optimize.
        #t_flatten = 0.0
        #t_check = 0.0
        #t_append = 0.0
        #t_copy = 0.0

        # Do some setup, including getting a repository key map cache so we don't have
        # to look up repository keys all the time. This is a huge overhead without the
        # cache.
        airr_class = self.getAIRRMap().getExpressionClass()
        repository_keymap = dict()

        # Iterate over the expression records in the array.
        for airr_expression_dict in expression_array:

            # When we load into an iReceptor repository, we flatten out all AIRR
            # contructs into a simple, flat representation. ir_flatten performs this.
            # Unforuntately, when we have millions of records, it is too inefficient. 
            # So we do some local caching of key look ups and we don't check the type
            # of the data put into the repository. For GEX they are all strings except
            # the `value` field.
            #
            # Create a copy of the orginal dictionary
            #t_local_start = time.perf_counter()
            original_dict = airr_expression_dict.copy()
            #t_local_end = time.perf_counter()
            #t_copy = t_copy + (t_local_end - t_local_start)
            #t_local_start = time.perf_counter()

            # Iterate over the original dictionay.
            for key, value in original_dict.items():
                # If the key is a dictionary we know it is an CURIE with a label and ID.
                # In GEX data this is the `property` but we generalize the dictionary
                # handling in case this changes.
                if isinstance(value, dict):
                    # Get rid of the original key value
                    airr_expression_dict.pop(key)
                    # Check to see if the key is in the map and if so use it, if not
                    # generate the repository key and add it to the repository keymap.
                    if not key in repository_keymap:
                        rep_key = self.fieldToRepository(key, airr_class)
                        repository_keymap[key] = rep_key
                    else:
                        rep_key = repository_keymap[key]
                    # Add the repository key and assign the original CURIE label
                    airr_expression_dict[rep_key] = value['label']
                    # Now we repeat for the ID of the CURIE. In the iReceptor repository
                    # CURIEs are flattened and the ID field is the key with _id as a suffix
                    key_id = key + '_id'
                    # Check to see if the key is in the map and if so use it, if not
                    # generate the repository key and add it to the repository keymap.
                    if not key_id in repository_keymap:
                        rep_key = self.fieldToRepository(key_id, airr_class)
                        repository_keymap[key_id] = rep_key
                    else:
                        rep_key = repository_keymap[key_id]
                    # Add the repository key for the CURIE id and assign the CURIE ID field.
                    airr_expression_dict[rep_key] = value['id']
                else:
                    # If we get here we are simply mapping a key value pair.
                    # Check to see if the key is in the map and if so use it, if not
                    # generate the repository key and add it to the repository keymap.
                    if not key in repository_keymap:
                        rep_key = self.fieldToRepository(key, airr_class)
                        repository_keymap[key] = rep_key
                    else:
                        rep_key = repository_keymap[key]
                    # Replace the key with the repository and assign the value.
                    # NOTE: We are not checking the value type to confirm that it is correct
                    # according to the AIRR Spec, this is too expensive for GEX data and we
                    # know all fields should be strings.
                    airr_expression_dict.pop(key)
                    airr_expression_dict[rep_key] = value

            #t_local_end = time.perf_counter()
            #t_flatten = t_flatten + (t_local_end - t_local_start)

            # Set the link field to link back to the repertoire object
            airr_expression_dict[rep_expression_link_field] = repertoire_link_id

            # Set the relevant IDs for the record being inserted. It updates the dictionary
            # (passed by reference) and returns False if it fails. If it fails, don't
            # load any data.
            #t_local_start = time.perf_counter()
            if (not self.checkIDFieldsJSON(airr_expression_dict, repertoire_link_id)):
                return False
            #t_local_end = time.perf_counter()
            #t_check = t_check + (t_local_end - t_local_start)

            # Create the created and update values for this record. Note that
            # this means that each block of inserts will have the same date.
            now_str = self.getDateTimeNowUTC()
            airr_expression_dict[ir_created_at] = now_str
            airr_expression_dict[ir_updated_at] = now_str

            # Insert a chunk of records into Mongo if we have a chunk ready.
            #t_local_start = time.perf_counter()
            block_array.append(airr_expression_dict.copy())
            #t_local_end = time.perf_counter()
            #t_append = t_append + (t_local_end - t_local_start)

            # We want to insert into mongo in blocks of chunk_size records.
            block_count = block_count + 1
            if block_count == chunk_size:
                #t_insert_start = time.perf_counter()
                self.repositoryInsertRecords(block_array)
                #t_insert_end = time.perf_counter()
                t_end = time.perf_counter()

                #print("Info: insert time = %f"% (t_insert_end-t_insert_start),flush=True)
                #print("Info: flatten time = %f"% (t_flatten),flush=True)
                #print("Info: check time = %f"% (t_check),flush=True)
                #print("Info: append time = %f"% (t_append),flush=True)
                #print("Info: copy time = %f"% (t_copy),flush=True)
                print("Info: Inserted %d records, time = %f (%f records/s, %f percent)"%
                        (chunk_size, t_end-t_start, chunk_size/(t_end-t_start),
                        (total_records/expression_records)*100),flush=True)
                #t_flatten = 0
                #t_check = 0
                #t_append = 0
                #t_copy = 0
                block_count = 0
                block_array = []
                t_start = time.perf_counter()

            # Keep track of the total number of records processed.
            total_records = total_records + 1

        # Done the main loop, insert any remaining records that didn't get inserted
        # as a block.
        if block_count > 0:
            self.repositoryInsertRecords(block_array)
            t_end = time.perf_counter()
            print("Info: Inserted %d records, time = %f (%f records/s)"%
                    (block_count, t_end-t_start, block_count/(t_end-t_start)),flush=True)

        # Get the number of annotations for this repertoire 
        if self.verbose():
            print("Info: Getting the number of annotations for this repertoire")
        annotation_count = self.repositoryCountRecords(repertoire_link_id)
        if annotation_count == -1:
            print("ERROR: invalid annotation count (%d), write failed." %
                  (annotation_count))
            return False

        # Set the cached expression count field for the repertoire/sample.
        if not self.repositoryUpdateCount(repertoire_link_id, annotation_count):
            print("ERROR: Unable to write expression count to repository.")
            return False

        # Inform on what we added and the total count for the this record.
        t_end_full = time.perf_counter()
        print("Info: Inserted %d records, annotation count = %d, %f s, %f insertions/s" %
              (total_records, annotation_count, t_end_full - t_start_full,
              total_records/(t_end_full - t_start_full)), flush=True)

        return True
        
