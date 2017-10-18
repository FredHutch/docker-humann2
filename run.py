#!/usr/bin/python
"""Analyze a set of samples with HUMAnN2."""

import os
import json
import uuid
import boto3
import shutil
import logging
import argparse
import subprocess


def run_cmds(commands):
    """Run commands and write out the log, combining STDOUT & STDERR."""
    logging.info("Commands:")
    logging.info(' '.join(commands))
    p = subprocess.Popen(commands,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    stdout, stderr = p.communicate()
    exitcode = p.wait()
    if stdout:
        logging.info("Standard output of subprocess:")
        for line in stdout.split('\n'):
            logging.info(line)
    if stderr:
        logging.info("Standard error of subprocess:")
        for line in stderr.split('\n'):
            logging.info(line)

    # Check the exit code
    assert exitcode == 0, "Exit code {}".format(exitcode)


def get_reads_from_url(input_str, temp_folder):
    """Get a set of reads from a URL."""
    logging.info("Getting reads from {}".format(input_str))
    error_msg = "{} must start with s3://, sra://, or ftp://".format(input_str)
    assert input_str.startswith(('s3://', 'sra://', 'ftp://')), error_msg

    filename = input_str.split('/')[-1]
    local_path = os.path.join(temp_folder, filename)

    logging.info("Filename: " + filename)
    logging.info("Local path: " + local_path)

    # Get files from AWS S3
    if input_str.startswith('s3://'):
        logging.info("Getting reads from S3")
        run_cmds(['aws', 's3', 'cp', '--quiet', '--sse', 'AES256',
                  input_str, temp_folder])
        return local_path

    # Get files from an FTP server
    elif input_str.startswith('ftp://'):
        logging.info("Getting reads from FTP")
        run_cmds(['wget', '-P', temp_folder, input_str])
        return local_path

    # Get files from SRA
    elif input_str.startswith('sra://'):
        accession = filename
        logging.info("Getting reads from SRA: " + accession)
        local_path = os.path.join(temp_folder, accession + ".fastq")
        # Download from NCBI
        run_cmds(["prefetch",
                  accession])
        run_cmds(["fastq-dump",
                  "--skip-technical",
                  "--readids",
                  "--read-filter",
                  "pass",
                  "--dumpbase",
                  "--clip",
                  "--outdir",
                  temp_folder,
                  accession])

        # Rename the file (which automatically has '_pass' included)
        run_cmds(["mv",
                  os.path.join(temp_folder, accession + "_pass.fastq"),
                  local_path])

        # Clean up the cached *.sra file
        if os.path.exists('/root/ncbi/public/sra/{}.sra'.format(accession)):
            logging.info("Deleting cached SRA file")
            os.unlink('/root/ncbi/public/sra/{}.sra'.format(accession))

        return local_path

    else:
        raise Exception("Did not recognize prefix for sample: " + input_str)


def get_reference_database(ref_db, temp_folder):
    """Get a reference database."""

    # Get files from AWS S3
    if ref_db.startswith('s3://'):
        logging.info("Getting reference database from S3: " + ref_db)

        # Save the database to a local folder with a random string prefix
        random_string = uuid.uuid4()
        local_fp = os.path.join(temp_folder, "{}.db".format(random_string))

        assert os.path.exists(local_fp) is False

        logging.info("Saving database to " + local_fp)
        # Using `sync` so that the entire folder structure is copied
        run_cmds(['aws', 's3', 'sync', '--quiet', '--sse', 'AES256',
                  ref_db, local_fp])

        # If the database was downloaded from S3, delete it when finished
        delete_db_when_finished = True

        return local_fp, delete_db_when_finished

    else:
        # Treat the input as a local path
        logging.info("Getting reference database from local path: " + ref_db)
        assert os.path.exists(ref_db)

        # Don't delete this database when finished
        delete_db_when_finished = False

        return ref_db, delete_db_when_finished


def return_results(out, read_prefix, output_folder, temp_folder):
    """Write out the final results as a JSON object in the output folder."""
    # Make a temporary file
    temp_fp = os.path.join(temp_folder, read_prefix + '.json')
    with open(temp_fp, 'wt') as fo:
        json.dump(out, fo)
    # Compress the output
    run_cmds(['gzip', temp_fp])
    temp_fp = temp_fp + '.gz'

    if output_folder.startswith('s3://'):
        # Copy to S3
        run_cmds(['aws', 's3', 'cp', '--quiet', '--sse', 'AES256',
                  temp_fp, output_folder])
    else:
        # Copy to local folder
        run_cmds(['mv', temp_fp, output_folder])


def control_file_endings(input_file):
    """HUMAnN2 has a quirk in that it requires a defined file suffix."""
    for suffix, replacement in [('.fna', '.fasta'),
                                ('.fa', '.fasta'),
                                ('.fq', '.fastq'),
                                ('.fna.gz', '.fasta.gz'),
                                ('.fa.gz', '.fasta.gz'),
                                ('.fq.gz', '.fastq.gz')]:
        if input_file.endswith(suffix):
            new_file = input_file.replace(suffix, replacement)
            os.rename(input_file, new_file)
            return(new_file)
    return input_file


def run(input_str,           # ID for single sample to process
        db_fp,               # Local path to DB
        db_url,              # URL of ref DB, used for logging
        output_folder,       # Place to put results
        temp_folder,         # Temporary folder
        threads):            # Number of threads
    """Run HUMAnN2 on a single sample and return the results."""

    # Use the read prefix to name the output and temporary files
    read_prefix = input_str.split('/')[-1]

    # Check to see if the output already exists, if so, skip this sample
    output_fp = output_folder.rstrip('/') + '/' + read_prefix + '.json.gz'
    if output_fp.startswith('s3://'):
        # Check S3
        logging.info("Making sure that the output path doesn't already exist")
        bucket = output_fp[5:].split('/')[0]
        prefix = '/'.join(output_fp[5:].split('/')[1:])
        client = boto3.client('s3')
        results = client.list_objects(Bucket=bucket, Prefix=prefix)
        if 'Contents' in results:
            logging.info("Output already exists ({})".format(output_fp))
            return
    else:
        # Check local filesystem
        if os.path.exists(output_fp):
            logging.info("Output already exists ({})".format(output_fp))
            return

    # Get the sample
    input_file = get_reads_from_url(input_str, temp_folder)

    # If the file ends with some non-standard file endings, correct them
    input_file = control_file_endings(input_file)

    # Run HUMAnN2
    run_cmds(["humann2", "--input", input_file, "--output", temp_folder,
              "--nucleotide-database", os.path.join(db_fp, "chocophlan"),
              "--protein-database", os.path.join(db_fp, "uniref"),
              "--threads", str(threads)])

    # Collect the output
    out = read_humann2_output_files(temp_folder)

    # Add the runtime parameters
    out["parameters"] = {"db": db_url, "input": input_str, "threads": threads}

    # Read in the logs
    logging.info("Reading in the logs")
    out["logs"] = open(log_fp, 'rt').readlines()

    # Write out the final results as a JSON object to the output folder
    return_results(out, read_prefix, output_folder, temp_folder)


def read_humann2_output_files(output_folder):
    """Look in a particular output folder and return the set of results."""
    out = {}

    for file in os.listdir(output_folder):
        if file.endswith("_genefamilies.tsv"):
            # This is the gene family abundance file
            msg = "Multiple *_genefamily.tsv files"
            assert "gene_families" not in out, msg
            out["gene_families"] = read_tsv(os.path.join(output_folder, file),
                                            header=["gene_family", "RPK"])
        elif file.endswith("_pathabundance.tsv"):
            # This is the pathway abundance file
            msg = "Multiple *_pathabundance.tsv files"
            assert "pathway_abund" not in out, msg
            out["pathway_abund"] = read_tsv(os.path.join(output_folder, file),
                                            header=["pathway", "abund"])
        elif file.endswith("_pathcoverage.tsv"):
            # This is the gene family abundance file
            assert "pathway_cov" not in out, "Multiple *pathcoverage.tsv files"
            out["pathway_cov"] = read_tsv(os.path.join(output_folder, file),
                                          header=["pathway", "cov"])

    # Make sure that all of the outputs were found
    for k in ["gene_families", "pathway_abund", "pathway_cov"]:
        assert k in out

    return out


def read_tsv(fp, header=None, comment_char="#", sep="\t"):
    """Read any given TSV."""
    out = []
    if header is None:
        # If no header is passed in, read the first line and use those values
        skip_first_line = True
        with open(fp, "rt") as f:
            header = f.readline().rstrip("\n").lstrip('#').split(sep)
    else:
        skip_first_line = False
    # Read in each line, and add it to the output
    with open(fp, "rt") as f:
        for ix, line in enumerate(f):
            # If the first line was used as a header, skip it
            if skip_first_line and ix == 0:
                continue
            # Skip lines starting with comment characters
            elif line[0] == comment_char:
                continue
            # Skip empty lines
            elif len(line.strip("\n")) == 0:
                continue
            else:
                fields = line.rstrip("\n").split(sep)
                assert len(fields) == len(header)
                # Add the fields to the output as a dict
                out.append(dict(zip(header, fields)))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""
    Analyze a set of reads with HUMAnN2 and save the results.
    """)

    parser.add_argument("--input",
                        type=str,
                        help="""Location for input file(s). Comma-separated.
                                (Supported: sra://, s3://, or ftp://).""")
    parser.add_argument("--ref-db",
                        type=str,
                        help="""Folder containing reference database.
                                (Supported: s3://, ftp://, or local path).""")
    parser.add_argument("--output-folder",
                        type=str,
                        help="""Folder to place results.
                                (Supported: s3://, or local path).""")
    parser.add_argument("--temp-folder",
                        type=str,
                        default='/share',
                        help="Folder used for temporary files.")
    parser.add_argument("--threads",
                        type=int,
                        default=1,
                        help="Number of threads to use for analysis.")

    args = parser.parse_args()

    # Set up logging
    log_fp = str(uuid.uuid4()) + '.log.txt'
    fmt = '%(asctime)s %(levelname)-8s [run.py] %(message)s'
    logFormatter = logging.Formatter(fmt)
    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.INFO)

    # Write to file
    fileHandler = logging.FileHandler(log_fp)
    fileHandler.setFormatter(logFormatter)
    rootLogger.addHandler(fileHandler)
    # Also write to STDOUT
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    rootLogger.addHandler(consoleHandler)

    # Get the reference database
    db_fp, delete_db_when_finished = get_reference_database(args.ref_db,
                                                            args.temp_folder)
    logging.info("Reference database: " + db_fp)
    # Make sure that each of the two subfolders exist
    assert os.path.exists(os.path.join(db_fp, "chocophlan"))
    assert os.path.exists(os.path.join(db_fp, "uniref"))

    logging.info("Threads: {}".format(args.threads))

    # Align each of the inputs and calculate the overall abundance
    for input_str in args.input.split(','):
        # Make a new temp folder for this set of results
        temp_folder = os.path.join(args.temp_folder, str(uuid.uuid4()))
        os.mkdir(temp_folder)
        logging.info("Processing input argument: " + input_str)
        # Run HUMAnN2
        run(input_str,                     # ID for single sample to process
            db_fp,                         # Local path to DB
            args.ref_db,                   # URL of ref DB, used for logging
            args.output_folder,            # Place to put results
            threads=args.threads,          # Number of threads
            temp_folder=temp_folder)       # Temporary folder
        # Delete the temporary folder
        shutil.rmtree(temp_folder)

    # Delete the reference database
    if delete_db_when_finished:
        logging.info("Deleting reference database: {}".format(db_fp))
        shutil.rmtree(db_fp)

    # Stop logging
    logging.info("Done")
    logging.shutdown()