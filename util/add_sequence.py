import pymongo
import re
import tarfile
import zipfile
import gzip
from Bio import SeqIO
from Bio import Seq
import os
import sys
from os import listdir
from os.path import isfile, join
import shutil

def loadData(path, filename):
    fullname = path + filename;
    filelist = []
#    if fullname.endswith(".zip"):
#        f= zipfile.ZipFile(fullname)
#        filelist = f.namelist() 
        #f.extractall()
#    elif fullname.endswith(".gz"):
#        f= tarfile.open(fullname, 'r') 
#        filelist = f.getnames()
#        #f.extractall()
#    elif fullname.endswith(".fasta"):
#        filelist.push(fullname)
#    else:
#        print("Unknown file")
#        return();
    print ("Processing " + fullname)
    counter = 0;
    tempfile = mypath + "temp.fasta";
    with gzip.open(fullname) as f:
        with open(tempfile, "wb") as out:
            shutil.copyfileobj(f, out)	
        for record in SeqIO.parse(tempfile, "fasta"):
             header = record.description
             imgt_header = re.sub(r'\s', "_", header)
             imgt_header = imgt_header[0:50]
             sequence = str(record.seq)
             update_query = sequence_db_cm.update({"seq_name":header}, {"$set": {"sequence":sequence}})
             if (update_query['nModified'] == 0):
                 update_query = sequence_db_cm.update({"seq_name":imgt_header}, {"$set": {"sequence":sequence}})
                 if (update_query['nModified'] == 0):
                      print("Header + " + header + " converted to " + imgt_header+ " not found!")
             counter+=1
             if(counter%200000 == 0):
                   print("Processed " + str(counter) + " lines")
      
    os.remove(tempfile)
     

def main(mypath):
    onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]
    for filename in onlyfiles:
        loadData(mypath,filename)

if __name__ == "__main__":
    mng_client = pymongo.MongoClient('localhost', 27017)
    db_name = sys.argv[1]
    sequence_cname = sys.argv[2]
    mypath = sys.argv[3]
    # Replace mongo db name
    mng_db = mng_client[db_name]
    #  Replace mongo db collection name
    sequence_db_cm = mng_db[sequence_cname]
    main(mypath)

