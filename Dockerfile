FROM registry.access.redhat.com/ubi8/ubi:8.5-236.1648460182

# install python modules
COPY requirements.txt /
#RUN pip install -r /requirements.txt

# switch for root user for the installations
USER root
ARG user=appuser
ARG group=appuser
ARG uid=1000
ARG gid=1000
RUN groupadd -g ${gid} ${group}
RUN useradd -u ${uid} -g ${group} -s /bin/sh -m ${user} # <--- the '-m' create a user home directory

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
RUN pip3.6 install -r /requirements.txt
# install the php dependencies 
RUN yum -y install php php-devel php-pear php-json && yum -y clean all
RUN pecl install mongodb
RUN php -v
RUN echo "extension=mongodb.so" >> /etc/php.ini
RUN curl -sS https://getcomposer.org/installer |php
RUN mv composer.phar /usr/local/bin/composer

# switch to user
USER ${uid}:${gid}
# set working directory
WORKDIR /home/appuser

RUN cd ~
RUN mkdir ~/app ~/config ~/app/config
RUN composer require mongodb/mongodb
# add this folder to the Docker image
COPY . ~/app
RUN ln -s ~/config/AIRR-iReceptorMapping.txt ~/app/config/AIRR-iReceptorMapping.txt

