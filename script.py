#!/usr/bin/python3
# You should change the shebang above to your custom virtual environment

import os
import subprocess
import paramiko
import tqdm
import argparse
import logging
import shutil
import glob
from datetime import datetime

PART_SIZE = 6 * 1024 * 1024 * 1024  # 6GB in bytes

def check_tmp_directory():
    tmp_dir = "/home/tmp/"
    if not os.path.exists(tmp_dir):
        logging.error(f"Directory {tmp_dir} does not exist")
        return False
    if not os.access(tmp_dir, os.W_OK):
        logging.error(f"No write permission in {tmp_dir}")
        return False
    total, used, free = shutil.disk_usage(tmp_dir)
    if free < PART_SIZE:
        logging.error(f"Not enough free space in {tmp_dir}. Free: {free}, Required: {PART_SIZE}")
        return False
    return True

def get_directory_size(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def compress_directory(source_dir, verbose, use_gzip, part_size):
    source_dir = os.path.abspath(os.path.expanduser(source_dir))
    output_base = f"/home/tmp/backup_{os.path.basename(source_dir)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    tar_options = "cfz" if use_gzip else "cf"
    extension = "tar.gz" if use_gzip else "tar"

    cmd = f"tar -{tar_options} - -C {source_dir} . | split -b {part_size} - {output_base}.{extension}."

    logging.info(f"Executing command: {cmd}")

    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    
    if result.returncode != 0:
        logging.error(f"Compression failed with return code {result.returncode}")
        logging.error(f"stderr: {result.stderr}")
        raise Exception("Compression failed")

    logging.info("Compression completed successfully")

    # Use glob to find all created backup files
    files = glob.glob(f"{output_base}.{extension}.*")
    
    if not files:
        logging.warning("No output files were created")
    else:
        logging.info(f"Created files: {', '.join(files)}")

    return files

def transfer_file(local_path, verbose, host, remote_path):
    if remote_path:
        remote_file_path = os.path.join(remote_path, os.path.basename(local_path))
    else:
        remote_file_path = f"/home/llucsm/backups/{os.path.basename(local_path)}"

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host)

        sftp = ssh.open_sftp()

        file_size = os.path.getsize(local_path)
        
        if verbose:
            sftp.put(local_path, remote_file_path, callback=lambda transferred, total: print(f"Transferred: {transferred}/{total}"))
        else:
            with tqdm.tqdm(total=file_size, unit='B', unit_scale=True, desc=f"Transferring {os.path.basename(local_path)}") as pbar:
                sftp.put(local_path, remote_file_path, callback=lambda transferred, total: pbar.update(transferred - pbar.n))

        sftp.close()
        ssh.close()
        return True
    except Exception as e:
        logging.error(f"Error transferring file {os.path.basename(local_path)}: {str(e)}")
        return False

def get_transfer_only_files():
    tmp_dir = "/home/tmp/"
    return glob.glob(f"{tmp_dir}backup_*.tar.gz.*")

def print_summary(args):
    summary = ["Summary of actions:"]
    
    if args.transfer_only:
        summary.append("- Transfer existing backup files from /home/tmp/ to the specified host")
    elif args.compress_only:
        summary.append(f"- Compress the directory: {args.source}")
        summary.append("- Files will be saved in /home/tmp/")
        if args.gzip:
            summary.append("- Using gzip compression")
    else:
        summary.append(f"- Compress the directory: {args.source}")
        if args.gzip:
            summary.append("- Using gzip compression")
        summary.append(f"- Transfer compressed files to {args.host}")
        summary.append("- Remove temporary files after successful transfer")
    
    if args.verbose:
        summary.append("- Verbose mode: Detailed output will be displayed")
    
    if args.part_size:
        summary.append(f"- Using custom part size: {args.part_size} bytes")
    
    if args.host != 'home_server':
        summary.append(f"- Using custom host: {args.host}")
    
    if args.remote_path:
        summary.append(f"- Using custom remote path: {args.remote_path}")
    
    print("\n".join(summary))

def get_user_confirmation():
    while True:
        response = input("Do you want to proceed? (Y/n): ").lower().strip()
        if response in ['', 'y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Invalid input. Please enter 'Y' or 'n'.")

def main():
    parser = argparse.ArgumentParser(prog="Acrilique's backup script", description="Backup and transfer a specified directory to the home_server host", epilog="The home_server host should have a folder called /home/llucsm/backups/ to store the files")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed output")
    parser.add_argument("-t", "--transfer-only", action="store_true", help="Transfer existing files without compression")
    parser.add_argument("-z", "--gzip", action="store_true", help="Use gzip compression (adds 'z' to tar command)")
    parser.add_argument("-c", "--compress-only", action="store_true", help="Compress without transferring")
    parser.add_argument("-s", "--source", default="~", help="Source directory to backup (default: home directory)")
    parser.add_argument("-p", "--part-size", type=int, default=PART_SIZE, help="Part size in bytes (default: 6GB)")
    parser.add_argument("--host", default="home_server", help="Host to send the files to (default: home_server)")
    parser.add_argument("--remote-path", help="Absolute remote path to send the files to (default: /home/llucsm/backups/)")
    args = parser.parse_args()

    logging.basicConfig(filename='backup.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Print summary and get user confirmation
    print_summary(args)
    if not get_user_confirmation():
        print("Operation cancelled by user.")
        return

    try:
        if args.transfer_only:
            if args.compress_only:
                logging.error("Cannot use both --transfer-only and --compress-only options")
                print("Error: Cannot use both --transfer-only and --compress-only options")
                return
            logging.info("Running in transfer-only mode")
            files_to_transfer = get_transfer_only_files()
            if not files_to_transfer:
                logging.warning("No files found for transfer in /home/tmp/")
                print("No files found for transfer in /home/tmp/")
                return
        else:
            logging.info("Starting compression")
            if not check_tmp_directory():
                raise Exception("Cannot proceed due to issues with /home/tmp/")
            files_to_transfer = compress_directory(args.source, args.verbose, args.gzip, args.part_size)

        logging.info(f"Files to transfer: {', '.join(files_to_transfer)}")

        if not args.compress_only:
            for file in files_to_transfer:
                logging.info(f"Starting transfer of {file}")
                if transfer_file(file, args.verbose, args.host, args.remote_path):
                    logging.info(f"Transfer of {file} completed")
                    if not args.transfer_only:
                        os.remove(file)
                        logging.info(f"Temporary file removed: {file}")
                else:
                    logging.error(f"Transfer of {file} failed. File not removed.")
        else:
            logging.info("Compression completed. Files not transferred due to --compress-only option.")
            print("Compression completed. Files not transferred due to --compress-only option.")

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        print(f"An error occurred. Check backup.log for details.")

if __name__ == "__main__":
    main()
