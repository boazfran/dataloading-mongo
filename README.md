# dataloading-mongo

Here we give an overview of iReceptor node data loading configuration and operation. 
It is assumed that you type in these commands and run them within a Linux terminal
running within the Linux machine which has your Mongo database. 
(note that the '$' designates the terminal command line prompt... your prompt may look different!).

This tutorial assumes that you are running a Linux version like Ubuntu
(adjust the installation instructions to suit your particular Linux flavor...).

# Prerequisites

If you are running the scripts directly on your host system, you should consider running
them within a [virtualenv](https://virtualenv.pypa.io/en/stable/installation/).
To install virtualenv, you will need to first install the regular (i.e. Python 2) version
of pip. Since the data loading script is written to run under the release 3 of Python, you should
ensure that it is also installed on your system. You will also need to install the latest version of 
[pip3](https://pip.pypa.io/en/stable/installing/) - the Python 3 variant of pip

```
$ sudo apt install python-pip
$ sudo pip install virtualenv

# also install Python3 if it is not already 
# pre-installed by your Linux OS version, then...
$ sudo apt install python3-pip
$ pip3 install --upgrade pip # gets the latest version
```

If you are using another version of Linux, consult your respective operating 
system documentation for pip3 installation details.

# Running Virtualenv

The full user guide for virtualenv (https://virtualenv.pypa.io/en/stable/userguide/) is available, but
for our purposes, the required operation is simply to create a suitable location and initialize it 
with the tool.. The one important detail to remember is to make Python3 the default Python interpreter 
used by the environment:

```
$ sudo mkdir -p /opt/ireceptor/data

# make sure your regular Linux account, not root, owns the directory
$ sudo chown ubuntu:ubuntu /opt/ireceptor/data

$ cd /opt/ireceptor

# make sure you specific Python3 as the default...
$ virtualenv --python=python3 data

$ cd data
$ source bin/activate

# you should now be running within a virtual environment inside 'data'
# Note that the command line prompt will change to something like the following:
(data) ubuntu@...:/opt/ireceptor/data$

# where the .. is some hostname stuff specific to your operating system shell configuration.
# If you decide to use virtualenv, then from this point onward the '$' command line prompt 
is assumed to be the virtualenv prompt, unless stated otherwise

# To exit the virtualenv, type the following
$ deactivate
```

You should now be back to your normal Linux system shell prompt.
To re-enter virtualenv, rerun the *source bin/activate* command as above,
from within the /opt/ireceptor/data subdirectory

For convenience, if you haven't already done so, it is also helpful to configure a Linux symbolic file link 
nearby, pointing to your local git cloned copy of the turnkey-service repository.something like:

```
$ sudo ln -s /path/to/your/cloned/turnkey-service /opt/ireceptor/turnkey-service
```

We assume this aliased location of the turnkey code in some of our commands which follow below.
(Modify those commands to suit the actual turnkey-service code (symbolic link) location that you decide to use).

# Installing Dependencies

The data loading scripts use several Python 3 libraries. These are listed 
in the pip 'requirements.txt' file and may be installed as follows:

```
# if you are using virtualenv, make sure that it is activated
$ cd /opt/ireceptor/data
$ source bin/activate

$ cd /opt/ireceptor/turnkey-service/dataloading
$ sudo pip3 install -r requirements.txt
```

# Test Data

To use the data loader, we obviously need some data! 

If you don't already have some suitably formatted data on hand but need to test your (Mongo) iReceptor node installation, 
you may use some test data files that we provide in the 'testdata' subdirectory provided here and which are documented in 
a README file in that subdirectory.

# Running the loading script

You should now be  

Note that the data loading script accesses the database using the 'service' (**NOT** the 'guest') account username and password ("secret") that you will have specified while setting up the MongoDb database.  You need to specify these either as options on the command line or set as environment variables (see below).  You can use the -h / --help flag to display the data loader usage, as follows:

```
$ ./ireceptor_data_loader.py -h  

Usage: ireceptor_data_loader.py [options]

Note: for proper data processing, project --samples metadata should
generally be read first into the database before loading other data types.

Options:
  --version             show program's version number and exit
  -h, --help            show this help message and exit
  -v, --verbose         

  Data Type Options:
    Options to specify the type of data to load.

    --sample            Load a sample metadata file (a 'csv' file with
                        standard iReceptor column headers).
    --imgt              Load a zip archive of IMGT analysis results.

  Database Connection Options:
    These options control access to the database.

    --host=HOST         MongoDb server hostname. If the MONGODB_HOST
                        environment variable is set, it is used. Defaults to
                        'localhost' otherwise.
    --port=PORT         MongoDb server port number. Defaults to 27017.
    -u USER, --user=USER
                        MongoDb service user name. Defaults to the
                        MONGODB_USER environment variable if set. Defaults to
                        'admin' otherwise.
    -p PASSWORD, --password=PASSWORD
                        MongoDb service user account secret ('password').
                        Defaults to the MONGODB_PASSWORD environment variable
                        if set. Defaults to empty string otherwise.
    -d DATABASE, --database=DATABASE
                        Target MongoDb database. Defaults to the MONGODB_DB
                        environment variable if set. Defaults to 'ireceptor'
                        otherwise.

  Data Source Options:
    These options specify the identity and location of data files to be
    loaded.

    -l LIBRARY, --library=LIBRARY
                        Path to 'library' directory of data files. Defaults to
                        the current working directory.
    -f FILENAME, --filename=FILENAME
                        Name of file to load. Defaults to a data file with the
                        --type name as the root name (appropriate file format
                        and extension assumed).

```

If this doesn't automatically work, then check first if the file's mode is set to mode 'executable':

```
$ chmod u+x ireceptor_data_loader.py
```

Then try again.

## Linux Environment Variables

Note also that the default parameters for this script may also be set as Linux environment variables, e.g.

```
$ export MONGODB_DB=ireceptor
$ export MONGODB_USER=<your-ireceptor-service-account-username>
$ export MONGODB_PASSWORD=<your-ireceptor-service-account-password>

```

The MONGODB_HOST variable defaults to 'localhost' which is normally ok (though you can change it if you wish to point to another MONGO instance outside of the docker one...).

If environment variables are set, then the corresponding command line parameters may be omitted while running the script.

# What kind of data can be loaded?

The ireceptor_data_loader currently accepts iReceptor sample metadata csv files and zip archives of IMGT data file output.

Assuming that your data files use the default names, then:

```
$ ./ireceptor_data_loader.py -v
```

will default to the --sample flag which loads a properly formatted *sample.csv* file into the database.

```
$ ./ireceptor_data_loader.py -v --imgt
```

will load a properly formatted *imgt.zip* sequence annotation into the database.

The expected data formats are described in more detail on the [iReceptor Data Curation repository site](https://github.com/sfu-ireceptor/dataloading-curation).


