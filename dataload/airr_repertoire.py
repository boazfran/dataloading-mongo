#!/usr/bin/python3

import pandas as pd
import json
import os
from datetime import datetime
from datetime import timezone
from repertoire import Repertoire
import airr

class AIRRRepertoire(Repertoire):
    
    # Constructor - call the parent class constructor.
    def __init__(self, verbose, repository_tag, repository_chunk, airr_map, repository):
        Repertoire.__init__(self, verbose, repository_tag, repository_chunk, airr_map, repository) 

    # This method is a recursive function that takes a key and value in a JSON
    # object and recursively flattens the values adding each element to the dictionary 
    # as it finds a "leaf node". Note a leaf node in general is a key value pair where
    # the value is not a compoud object (not a dict or a list). If it is not a leaf node
    # then the fucntion recurses on all of the elements in the dict or list. Note that
    # a leaf node is a bit complex and specialized based on both the AIRR spec and how
    # they are represented in the iReceptor repository. 
    def ir_flatten(self, key, value, dictionary, key_path):
        rep_class = self.getAIRRMap().getRepertoireClass()
        column = self.getAIRRTag()
        # If it is an integer, float, or bool we just use the key value pair.
        if isinstance(value, (int, float, bool)):
            if self.validAIRRFieldType(key, value, False):
                rep_key = self.fieldToRepository(key, rep_class)
                rep_value = self.valueToRepository(key, column, value, rep_class)
                dictionary[rep_key] = rep_value
            else:
                raise TypeError("AIRR type error for " + key)
        # If it is a string we just use the key value pair.
        elif isinstance(value, str):
            if self.validAIRRFieldType(key, value, False):
                rep_key = self.fieldToRepository(key, rep_class)
                rep_value = self.valueToRepository(key, column, value, rep_class)
                dictionary[rep_key] = rep_value
            else:
                raise TypeError("AIRR type error for " + key)
        elif isinstance(value, dict):
            # We need to handle the AIRR ontology terms. Ontologies have two fields in
            # their dictionary, a value and an id.
            if 'label' in value and 'id' in value:
                # In an ontology, the dictionary contains two fields, a value and an id.
                # We store this in the repository as the value field being the key and
                # the id field as having an _id suffix added to the key
                value_key = key
                id_key = key+"_id"

                # Check types of both the value and the id, convert the data type, and
                # add to the dictionary.
                if (self.validAIRRFieldType(value_key, value['label'], False) and
                    self.validAIRRFieldType(id_key, value['id'], False)):
                    rep_value = self.valueToRepository(value_key, column,
                                                       value['label'], rep_class)
                    dictionary[self.fieldToRepository(value_key,rep_class)] = rep_value
                    rep_value = self.valueToRepository(id_key, column,
                                                       value['id'], rep_class)
                    dictionary[self.fieldToRepository(id_key, rep_class)] = rep_value
                else:
                    raise TypeError(key)
            else:
                #repo_key = self.getAIRRMap().getMapping(key,
                #                              self.getAIRRTag(), "ir_repository")
                #repo_type = self.getAIRRMap().getMapping(key,
                #                              self.getAIRRTag(), "ir_repository_type")
                #airr_type = self.getAIRRMap().getMapping(key,
                #                                  self.getAIRRTag(), "airr_type")
                repo_key = self.getAIRRMap().getMapping(key_path,
                                              "ir_adc_api_query", "ir_repository")
                repo_type = self.getAIRRMap().getMapping(key_path,
                                              "ir_adc_api_query","ir_repository_type")
                airr_type = self.getAIRRMap().getMapping(key_path,
                                              "ir_adc_api_query","airr_type")
                # If the AIRR field from the file is marked for storage as an object
                # and the repository can accept the object as an object, then we 
                # can save the object directly as an object. 
                if (repo_type == "object" and airr_type == "object"):
                    print("Info: Storing field %s as object %s (%s,%s, %s)"%(key, repo_key, airr_type, repo_type, key_path))
                    #if self.validAIRRFieldType(key, value, False):
                    #    rep_key = self.fieldToRepository(key, rep_class)
                    #    rep_value = self.valueToRepository(key, column, value, rep_class)
                    #    dictionary[rep_key] = rep_value
                    #else:
                    #    raise TypeError(key)
                    dictionary[repo_key] = value
                else:
                    # If we aren't storing as an object, we continue to flatten
                    for sub_key, sub_value in value.items():
                        self.ir_flatten(sub_key, sub_value, dictionary, key_path + "." + sub_key)
        elif isinstance(value, list):
            # There are currently three possible list situations in the spec. 
            # - keywords_study, data_processing_files: An array of strings
            #   that should be concatenated
            # - diagnosis: We only support one per repertoire. Warn and continue with 1st
            # - pcr_target: We only support one per repertoire. Warn and continue with 1st
            # - data_processing: We only support one per repertoire. Warn and continue
            #   with 1st data processing

            # We flatten this explicitly as a special case. We want to store the list
            # of strings.
            if key == "keywords_study" or key == "data_processing_files" or key == "germline_alleles":
                # TODO: Need to implement type checking on this field...
                
                if self.validAIRRFieldType(key, value, False):
                    rep_key = self.fieldToRepository(key, rep_class)
                    rep_value = self.valueToRepository(key, column, value, rep_class)
                    dictionary[rep_key] = rep_value
                else:
                    raise TypeError(key)
            else:
                # If we are handling a data processing element list, we have a hint as 
                # to which element is the most important, as we can use the
                # "primary_annotation" field to determine which one to use.
                if key == "data_processing":
                    # Warn if we found more than one, as we only store one per repertoire. If
                    # you have more than one and want to store the rearrangements separately
                    # then you need to split this up into two repertoires.
                    if len(value) > 1:
                        print("Warning: Found more than one %s element (found %d)."%
                              (key, len(value)))
                    # Look for the primary annotation
                    got_primary = False
                    for element in value:
                        if 'primary_annotation' in element and element['primary_annotation']:
                            # If we found it, flatten it and the break out of the loop
                            for sub_key, sub_value in element.items():
                                self.ir_flatten(sub_key, sub_value, dictionary, key_path + "." + sub_key)
                            got_primary = True
                            print("Info: Found a primary annotation, using it.")
                            break
                    # If we didn't find the primary, then use the first one as a best guess.
                    if not got_primary:
                        print("Warning: Could not find a primary annotation, using the first one.")
                        for sub_key, sub_value in value[0].items():
                            self.ir_flatten(sub_key, sub_value, dictionary, key_path + "." + sub_key)
                else:
                    repo_type = self.getAIRRMap().getMapping(key,
                                                  self.getAIRRTag(), "ir_repository_type")
                    airr_type = self.getAIRRMap().getMapping(key,
                                                  self.getAIRRTag(), "airr_type")
                    # If the AIRR field from the file is marked for storage as an object
                    # and the repository can accept the object as an object, then we 
                    # can save the object directly as an object. 
                    if (repo_type == "object" and airr_type == "object"):
                        print("Info: Storing field %s as an array of objects (%s,%s)"%(key, airr_type, repo_type))
                        #if self.validAIRRFieldType(key, value, False):
                        #    rep_key = self.fieldToRepository(key, rep_class)
                        #    rep_value = self.valueToRepository(key, column, value, rep_class)
                        #    dictionary[rep_key] = rep_value
                        #else:
                        #    raise TypeError(key)
                        dictionary[key] = value
                    else:
                        # In the general case, iReceptor only supports a single instance in 
                        # array subtypes. If this occurs, we generate an error message and
                        # stop processing by raising an exception on this key.
                        if len(value) > 1:
                            print("ERROR: Found a repertoire list for %s > 1 (%d)."%
                                  (key, len(value)))
                            print("ERROR: iReceptor only supports arrays of objects with one element.")
                            raise TypeError(key)
                        for sub_key, sub_value in value[0].items():
                            self.ir_flatten(sub_key, sub_value, dictionary, key_path + "." + sub_key)
        return dictionary

    def process(self, filename):

        # Check to see if we have a file    
        if not os.path.isfile(filename):
            print("ERROR: input file " + filename + " is not a file")
            return False

        # Get the column tag for the iReceptor mapping
        ireceptor_tag = self.getiReceptorTag()

        # Get the column tag for the iReceptor mapping
        repository_tag = self.getRepositoryTag()

        # Check the validity of the repertoires from an AIRR perspective
        try:
            data = airr.load_repertoire(filename)
        except airr.ValidationError as err:
            print("Warning: AIRR repertoire validation failed for file %s - %s" %
                  (filename, err))
        except Exception as err:
            print("ERROR: AIRR repertoire validation failed for file %s - %s" %
                  (filename, err))
            return False

        # Get the fields to use for finding repertoire IDs, either using those IDs
        # directly or by looking for a repertoire ID based on a rearrangement file
        # name.
        repertoire_id_field = self.getRepertoireLinkIDField()
        repertoire_file_field = self.getRepertoireFileField()

        # The 'Repertoire' contains a dictionary for each repertoire.
        repertoire_list = []
        for repertoire in data['Repertoire']:
            repertoire_dict = dict()
            for key, value in repertoire.items():
                try:
                    self.ir_flatten(key, value, repertoire_dict, key)
                except TypeError as error:
                    print("ERROR: %s"%(error))
                    return False

            # Ensure that we have a correct file name to link fields. If we can't find it 
            # this is a fatal error as we can not link any data to this set repertoire,
            # so there is no point adding the repertoire...
            repository_file_field = self.getAIRRMap().getMapping(repertoire_file_field,
                                                    ireceptor_tag, repository_tag)
            # If we can't find a mapping for this field in the repository mapping, then
            # we might still be OK if the metadata spreadsheet has the field. If the fails, 
            # then we should exit.
            if repository_file_field is None or len(repository_file_field) == 0:
                print("Warning: No repository mapping for the rearrangement file field (%s)"
                      %(repertoire_file_field))
                repository_file_field = repertoire_file_field
    
            # If we can't find the file field for the rearrangement field in the repository, then
            # abort, as we won't be able to link the repertoire to the rearrangement.
            if not repository_file_field in repertoire_dict:
                print("ERROR: Could not find a repertoire file field in the metadata (%)"
                      %(repertoire_file_field))
                print("ERROR: Will not be able to link repertoire to rearrangement annotations")
                return False

            repertoire_list.append(repertoire_dict)
                
        # Iterate over the list and load records. Note that this code inserts all data
        # that was read in. That is, all of the non MiAIRR fileds that exist
        # are stored in the repository. So if the provided file has lots of extra fields
        # they will exist in the repository.
        # TODO: Ensure that all records are written as the correct type for the repository.
        for r in repertoire_list:
            if self.repositoryInsertRepertoire(r) is None: 
                return False

        # If we made it here we are DONE!
        return True
