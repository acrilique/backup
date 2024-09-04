# backup
Backup helper that makes a tarball with the desired part size and transfers it via sftp to a host

## Usage
You will need python3 installed in order to use this script. It can be done via your package manager like this:
(Debian/Ubuntu)
```bash
sudo apt install python3
```

You should then have installed the paramiko and tqdm packages via pip. My advice is to do it inside a virtual environment. An example of how to do this:
```bash
python3 -m venv ~/.venv
source ~/.venv/bin/activate
pip install paramiko
pip install tqdm
```

Then start the script like this:
```bash
./script.sh
```
**Attention:** if you have followed the steps to create a virtual environment (`python3 -m venv...`), you NEED to change the shebang (the first line of the script) to the path of the virtual environment (/home/youruser/.venv/bin/python if you directly used my command)
