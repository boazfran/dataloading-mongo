# Script for loading AIRR TSV formatted annotation file 
# into an iReceptor database. Note that the AIRR TSV parser
# is the default parser used for IgBLAST, but it can be used
# for normal AIRR TSV files as well as can be used for general
# file mapping by overriding the Rearragnement's file mapping using
# the Rearragnement.setFileMapping() method before calling the process() 
# method.

import os.path
import pandas as pd
import time
import json
import gzip
import airr

from parser import Parser
from rearrangement import Rearrangement
from airr.io import RearrangementReader
from airr.schema import ValidationError

class AIRR_TSV(Rearrangement):
    
    def __init__( self, verbose, repository_tag, repository_chunk, airr_map, repository):
        Rearrangement.__init__(self, verbose, repository_tag, repository_chunk, airr_map, repository)
        # The default annotation tool used for the AIRR parser is IgBLAST
        self.setAnnotationTool("IgBLAST")
        # The default column in the AIRR Mapping file is igblast. This can be
        # overrideen by the user should they choose to use a differnt set of
        # columns from the file.
        self.setFileMapping("igblast")

    # We nedd to convert the AIRR TSV T/F to our mechanism for storing functionality
    # which is 1/0 
    def functional_boolean(self, functionality):
        if functionality or functionality == "T":
            return True
        else:
            return False

    def process(self, filewithpath):

        # Check to see if the file exists and return if not.
        if not os.path.isfile(filewithpath):
            print("ERROR: Could not open file ", filewithpath)
            return False
        
        # Open, decompress then read(), if it is a gz archive
        if filewithpath.endswith(".gz"):
            if self.verbose():
                print("Info: Reading gzip file: "+filewithpath)
            with gzip.open(filewithpath, 'rt') as file_handle:
                # Use gzip to get a file handle in text mode. 
                success = self.processAIRRTSVFile(file_handle, filewithpath)
        else: # or get a normal file handle for the file directly.
            if self.verbose():
                print("Info: Reading text file: "+filewithpath)
            file_handle = open(filewithpath, "r")
            success = self.processAIRRTSVFile(file_handle, filewithpath)

        return success

    def processAIRRTSVFile( self, file_handle, path ):

        # Start a timer for performance reasons.
        t_start_full = time.perf_counter()

        # Get the AIRR Map object for this class (for convenience).
        airr_map = self.getAIRRMap()

        # Set the tag for the repository that we are using.
        repository_tag = self.getRepositoryTag()
        # Set the tag for the iReceptor identifier.
        ireceptor_tag = self.getiReceptorTag()

        # Get the fields to use for finding repertoire IDs, either using those IDs
        # directly or by looking for a repertoire ID based on a rearrangement file
        # name.
        repertoire_link_field = self.getRepertoireLinkIDField()
        rearrangement_link_field = self.getAnnotationLinkIDField()

        # Set the tag for the file mapping that we are using. Ths is essentially the
        # look up into the columns of the AIRR Mapping that we are using. For the IgBLAST
        # parser it is normally the "igblast" column (which is essentially the same as 
        # AIRR TSV), but it can be overridden by the user.
        filemap_tag = self.getFileMapping()

        # Set the size of each chunk of data that is inserted.
        chunk_size = self.getRepositoryChunkSize()

        # Validate the AIRR TSV file header. We do not validate the entire
        # file becasue that is too expensive of an operation.
        # Validate header by trying to read the first record. If it throws
        # an error then we have a problem.
        airr_reader = RearrangementReader(file_handle, validate=False, debug=True)
        airr_valid = True
        try:
            airr_iterator = iter(airr_reader)
            first_record = next(airr_iterator)
        except ValidationError as e:
            airr_valid = False
            print("ERROR: File %s is not a valid AIRR TSV file, %s"
                  %(path, e))
            return False
        if airr_valid:
            print("Info: File %s has a valid AIRR TSV header"%(path))

        # Get root filename from the path
        filename = os.path.basename(path)

        # Get the single, unique repertoire link id for the filename we are loading. If
        # we can't find one, this is an error and we return failure.
        repertoire_link_id = self.getRepertoireInfo(filename)
        if repertoire_link_id is None:
            print("ERROR: Could not link file %s to a valid repertoire"%(filename))
            return False

        # Extract the fields that are of interest for this file. Essentiall all non null
        # fields in the file. This is a boolean array that is T everywhere there is a
        # notnull field in the column of interest.
        map_column = airr_map.getRearrangementMapColumn(filemap_tag)
        fields_of_interest = map_column.notnull()

        # We select the rows in the mapping that contain fields of interest from the file.
        # At this point, file_fields contains N columns that contain our mappings for the
        # the specific formats (e.g. iReceptor, AIRR, VQuest). The rows are limited to 
        # only data that is relevant to the file format column of interest. 
        file_fields = airr_map.getRearrangementRows(fields_of_interest)

        # We need to build the set of fields that the repository can store. We don't
        # want to extract fields that the repository doesn't want.
        igblastColumns = []
        columnMapping = {}
        if self.verbose():
            print("Info: Dumping expected %s (%s) to repository mapping"%
                  (self.getAnnotationTool(),filemap_tag))
        for index, row in file_fields.iterrows():
            if self.verbose():
                print("Info:    %s -> %s"%(str(row[filemap_tag]),
                      str(row[repository_tag])))
            # If the repository column has a value for the field in the file, track the 
            # field from both the file and repository side.
            if not pd.isnull(row[repository_tag]):
                igblastColumns.append(row[filemap_tag])
                columnMapping[row[filemap_tag]] = row[repository_tag]
            else:
                print("Info:     Repository does not support " +
                      str(row[filemap_tag]) + ", not inserting into repository")

        # Get the field names from the file from the airr_reader object. 
        # Determing the mapping from the file input to the repository.
        finalMapping = {}
        for airr_field in airr_reader.fields:
            if airr_field in columnMapping:
                if self.verbose():
                    print("Info: Mapping %s field in file: %s -> %s"%
                          (self.getAnnotationTool(), airr_field,
                           columnMapping[airr_field]))
                finalMapping[airr_field] = columnMapping[airr_field]
            else:
                if self.verbose():
                    print("Info: No mapping for input " + self.getAnnotationTool() +
                          " field " + airr_field +
                          ", adding to repository without mapping.")

        # Determine if we are missing any repository columns from the input data.
        for igblast_column, mongo_column in columnMapping.items():
            if not igblast_column in airr_reader.fields:
                if self.verbose():
                    print("Info: Missing data in input " + self.getAnnotationTool() +
                          " file for " + igblast_column)

        # Create a reader for the data frame with step size "chunk_size"
        if self.verbose():
            print("Info: Processing raw data frame...")
        airr_df_reader = pd.read_csv(path, sep='\t', chunksize=chunk_size)

        # Iterate over the file with data frames of size "chunk_size"
        total_records = 0
        for airr_df in airr_df_reader:
            # Remap the column names. We need to remap because the columns may be in a 
            # differnt order in the file than in the column mapping.
            airr_df.rename(finalMapping, axis='columns', inplace=True)

            # Build the substring array that allows index for fast searching of
            # Junction AA substrings.
            junction_aa = airr_map.getMapping("junction_aa",
                                              ireceptor_tag, repository_tag)
            ir_substring = airr_map.getMapping("ir_substring",
                                               ireceptor_tag, repository_tag)
            ir_junc_aa_len = airr_map.getMapping("ir_junction_aa_length",
                                                 ireceptor_tag, repository_tag)
            if junction_aa in airr_df:
                if self.verbose():
                    print("Info: Retrieving junction AA and building substrings",
                          flush=True)
                airr_df[ir_substring] = airr_df[junction_aa].apply(
                                         Rearrangement.get_substring)

                # The AIRR TSV format doesn't have AA length, we want it in repository.
                if not (ir_junc_aa_len in airr_df):
                    if self.verbose():
                        print("Info: Computing junction amino acids length...",
                              flush=True)
                    airr_df[ir_junc_aa_len] = airr_df[junction_aa].apply(
                                                  Parser.len_null_to_null)

            # We need to look up the "known parameter" from an iReceptor perspective (the 
            # field name in the iReceptor column mapping and map that to the correct 
            # field name for the repository we are writing to.
            v_call = airr_map.getMapping("v_call", ireceptor_tag, repository_tag)
            d_call = airr_map.getMapping("d_call", ireceptor_tag, repository_tag)
            j_call = airr_map.getMapping("j_call", ireceptor_tag, repository_tag)
            ir_vgene_gene = airr_map.getMapping("ir_vgene_gene",
                                                 ireceptor_tag, repository_tag)
            ir_dgene_gene = airr_map.getMapping("ir_dgene_gene",
                                                 ireceptor_tag, repository_tag)
            ir_jgene_gene = airr_map.getMapping("ir_jgene_gene",
                                                 ireceptor_tag, repository_tag)
            ir_vgene_family = airr_map.getMapping("ir_vgene_family",
                                                 ireceptor_tag, repository_tag)
            ir_dgene_family = airr_map.getMapping("ir_dgene_family",
                                                 ireceptor_tag, repository_tag)
            ir_jgene_family = airr_map.getMapping("ir_jgene_family",
                                                 ireceptor_tag, repository_tag)

            # Build the v_call field, as an array if there is more than one gene
            # assignment made by the annotator.
            self.processGene(airr_df, v_call, v_call, ir_vgene_gene, ir_vgene_family)
            self.processGene(airr_df, j_call, j_call, ir_jgene_gene, ir_jgene_family)
            self.processGene(airr_df, d_call, d_call, ir_dgene_gene, ir_dgene_family)
            # If we don't already have a locus (that is the data file didn't provide one) 
            # then calculate the locus based on the v_call array.
            locus = airr_map.getMapping("locus", ireceptor_tag, repository_tag)
            if not locus in airr_df:
                airr_df[locus] = airr_df[v_call].apply(Rearrangement.getLocus)

            # Keep track of the reperotire id so can link each rearrangement to
            # a repertoire
            rep_rearrangement_link_field = airr_map.getMapping(rearrangement_link_field,
                                                    ireceptor_tag, repository_tag)
            airr_df[rep_rearrangement_link_field]=repertoire_link_id

            # Set the relevant IDs for the record being inserted. If it fails, don't
            # load any data.
            if not self.checkIDFields(airr_df, repertoire_link_id):
                return False

            # Create the created and update values for this block of records. Note that
            # this means that each block of inserts will have the same date.
            now_str = Rearrangement.getDateTimeNowUTC()
            ir_created_at = airr_map.getMapping("ir_created_at",
                                                 ireceptor_tag, repository_tag)
            ir_updated_at = airr_map.getMapping("ir_updated_at",
                                                 ireceptor_tag, repository_tag)
            airr_df[ir_created_at] = now_str
            airr_df[ir_updated_at] = now_str

            # Transform the data frame so that it meets the repository type requirements
            if not self.mapToRepositoryType(airr_df,
                                            airr_map.getRearrangementClass(),
                                            airr_map.getIRRearrangementClass()):
                print("ERROR: Unable to map data to the repository")
                return False

            # Insert the chunk of records into Mongo.
            num_records = len(airr_df)
            print("Info: Inserting", num_records, "records into Mongo...", flush=True)
            t_start = time.perf_counter()
            records = json.loads(airr_df.T.to_json()).values()
            self.repositoryInsertRecords(records)
            t_end = time.perf_counter()
            print("Info: Inserted records, time =", (t_end - t_start), "seconds",
                  flush=True)

            # Keep track of the total number of records processed.
            total_records = total_records + num_records
            print("Info: Total records so far =", total_records, flush=True)
 
        # Get the number of annotations for this repertoire (as defined by the
        # repertoire link id
        if self.verbose():
            print("Info: Getting the number of annotations for repertoire %s"%
                  (str(repertoire_link_id)))
        annotation_count = self.repositoryCountRecords(repertoire_link_id)
        if annotation_count == -1:
            print("ERROR: invalid annotation count (%d), write failed." %
                  (annotation_count))
            return False

        if self.verbose():
            print("Info: Annotation count = %d" % (annotation_count), flush=True)

        # Set the cached sequence count field for the repertoire.
        self.repositoryUpdateCount(repertoire_link_id, annotation_count)

        # Inform on what we added and the total count for the this record.
        t_end_full = time.perf_counter()
        print("Info: Inserted %d records, annotation count = %d, %f s, %f insertions/s" %
              (total_records, annotation_count, t_end_full - t_start_full,
               total_records/(t_end_full - t_start_full)), flush=True)

        return True;
