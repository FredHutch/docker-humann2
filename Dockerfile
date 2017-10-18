FROM ubuntu:16.04
MAINTAINER sminot@fredhutch.org

# Install prerequisites
RUN apt update && \
	apt-get install -y build-essential wget python python-pip unzip python-matplotlib && \
	pip install humann2==0.11.1 boto3==1.4.7 awscli argparse \
				numpy==1.9.0 scipy==0.14.0

# Install MetaPhlAn2
RUN cd /usr/local/bin && \
	wget https://www.dropbox.com/s/ztqr8qgbo727zpn/metaphlan2.zip && \
	unzip metaphlan2.zip && rm metaphlan2.zip

# Set the environment variables to include MetaPhlAn2
ENV PATH="/usr/local/bin/metaphlan2:${PATH}"
ENV mpa_dir="/usr/local/bin/metaphlan2"



# Install the SRA toolkit
RUN cd /usr/local/bin && \
	wget https://ftp-trace.ncbi.nlm.nih.gov/sra/sdk/2.8.2/sratoolkit.2.8.2-ubuntu64.tar.gz && \
	tar xzvf sratoolkit.2.8.2-ubuntu64.tar.gz && \
	ln -s /usr/local/bin/sratoolkit.2.8.2-ubuntu64/bin/* /usr/local/bin/ && \
	rm sratoolkit.2.8.2-ubuntu64.tar.gz

# Test the installation
RUN humann2_test --run-functional-tests-tools

# Use /share as the working directory
RUN mkdir /share
WORKDIR /share

# Add the run script to the PATH
# ADD run.py /usr/bin/
