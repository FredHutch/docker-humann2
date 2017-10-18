# docker-humann2
Docker image running HUMANN2


This image has installed a pinned version of HUMAnN2. 


To run HUMANnN2, use the `run.py` wrapper script, which will:

  * Download or connect to a reference database
  * Download or connect to a set of samples
  * Run HUMAnN2 on those samples
  * Return the results to a specified output location


### Reference Database

In order to download a reference database that can be used with this image, 
simply run the following commands within the image, where $DB_FOLDER is a 
mounted folder where you would like to save the database files.

  * `humann2_databases --download chocophlan full $DB_FOLDER`
  * `humann2_databases --download uniref uniref90_diamond $DB_FOLDER`
