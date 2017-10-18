# docker-humann2
Docker image running HUMANN2

[![Docker Repository on Quay](https://quay.io/repository/fhcrc-microbiome/humann2/status "Docker Repository on Quay")](https://quay.io/repository/fhcrc-microbiome/humann2)

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

### Parameters for run.py

The `run.py` script is intended to wrap up all of the inputs and outputs for 
running humann2, including downloading the reference database and cleaning
up temporary files after analyzing a batch of files. The options are as 
follows: 


  * `--input`: The file(s) to be analyzed. SRA accessions are specified as 
  `sra://<accession>`, files on AWS S3 are specified as `s3://<url>`, and
  other files can be downloaded from an FTP server as `ftp://<url>`. 
  Multiple files should be separated with a comma (no space). 

  * `--ref-db`: The reference database is a folder (either on S3 or a local
  path) that contains both the nucleotide (chocophlan) and protein (uniref) 
  portions of the database. If you give a S3 path, the script will download 
  the folder from S3 before starting and clean it up at the end.

  * `--output-folder`: The folder where the final output will be placed can
  either be a local path or an S3 bucket (`s3://<url>`). The output file 
  will be named for the input file as `<input_file_prefix>.json.gz`.

  * `--temp-folder`: A folder available within the Docker image that has 
  space for the database and temporary files (at least ~20-50Gb).

  * `--threads`: Number of threads to use during the alignments. 

### Output format

The output of the `run.py` script will be a compressed JSON file that wraps
up the three primary outputs of HUMAnN2:

  * Gene family abundance
  * Pathway abundance
  * Pathway coverage

The format of that JSON is:

```
{
	"gene_families": [
		{"gene_family": "<gene family name>", "RPK": <float>},
		...
	],
	"pathway_abund": [
		{"pathway": "<pathway name>", "abund": <float>},
		...
	],
	"pathway_cov": [
		{"pathway": "<pathway name>", "cov": <float>},
		...
	],
	"parameters": {
		"db": "<database URL>",
		"input": "<input string>",
		"threads": <threads>
	},
	"logs": [
		"<log text line 0>",
		"<log text line 1>",
		"<log text line 2>",
		...
	]
}
```

### Other notes

It doesn't appear to be possible to optimize the amount of memory used during
the analysis. It's probably safe to run this with about 25G of RAM, but it 
probably depends on the size of the input file and the number of hits in each
of the databases, based on my prior experience with DIAMOND.
