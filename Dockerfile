FROM registry.access.redhat.com/ubi8/ubi

# switch for root user for the installations
USER root

RUN yum -y update
# install the python packages
RUN INSTALL_PKGS="python36 python36-devel python3-virtualenv python3-setuptools python3-pip \
        nss_wrapper httpd httpd-devel mod_ssl mod_auth_gssapi \
        mod_ldap mod_session atlas-devel gcc-gfortran libffi-devel \
        libtool-ltdl enchant git" && \
    yum -y module enable python36:3.6 httpd:2.4 && \
    yum -y --setopt=tsflags=nodocs install $INSTALL_PKGS && \
    rpm -V $INSTALL_PKGS && \
    # Remove redhat-logos-httpd (httpd dependency) to keep image size smaller.
    rpm -e --nodeps redhat-logos-httpd && \
    yum -y clean all --enablerepo='*'

# install the python dependecies
COPY requirements.txt /.
RUN python3.6 -m pip install -r /requirements.txt

# install the php packages 
RUN INSTALL_PKGS="php php-devel php-pear php-json" && \
    yum -y install $INSTALL_PKGS && \
    rpm -V $INSTALL_PKGS && \
    yum -y clean all --enablerepo='*'

# instal the php dependencies
RUN pecl install mongodb
RUN php -v
RUN echo "extension=mongodb.so" >> /etc/php.ini
RUN curl -sS https://getcomposer.org/installer |php
RUN mv composer.phar /usr/local/bin/composer
RUN composer require mongodb/mongodb

# create working directory
RUN mkdir --p /app/config

# add this folder to the Docker image
COPY . /app/. 

# add mapping file
RUN mkdir /config
ADD https://raw.githubusercontent.com/sfu-ireceptor/config/master/AIRR-iReceptorMapping.txt /config/
RUN ln -s /config/AIRR-iReceptorMapping.txt /app/config/AIRR-iReceptorMapping.txt
RUN chmod 644 /app/config/AIRR-iReceptorMapping.txt

# set file permissions
RUN chgrp -R 0 /app
RUN chgrp -R 0 /config
RUN mkdir -p /scratch && chgrp -R 0 /scratch
RUN mkdir -p /root && chgrp -R 0 /root

# change to non-root user - just for cleaness, infact the openshift platform
# will run the docker as an arbitrary user beloning to the root group
USER 1001

# set working directory
WORKDIR /root

# prevent pod from exiting
CMD tail -f /dev/null

