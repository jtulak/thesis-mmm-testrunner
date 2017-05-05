Test Runner
===========
A set of scripts to run the tests.

Installation
------------
Run `prepare.sh` to clone the other repositories needed for this.
Then run: `test.py -h`

Running the tests
-----------------
`./tests.py --path PATH_TO_XFSPROGS REVISION1 [REVISION2 ...]` or see `--help`
for more details.

The output is saved into `output` directory. If this directory already exists,
    then the existing one is renamed to `output.bak`, so it gives you a chance
    to do not lose data. Existing `output.bak` is deleted, though.

An example how to use it, that is used in my thesis, is:
```
./tests.py 07a3e793 d7e1f5f1 09033e35 6aa32b47..2aca16d6
```
In this example, the path is ommited, because xfsprogs is located in the
default location `../xfsprogs-dev/`.

Preprocessing the outputs
-------------------------
After the raw outputs were generated, run `./format-outputs.sh
DIR_WITH_RESULTS` (which by default would be `./format-outputs.sh ./output`).

This script does some formatting and preprocessing of the raw outputs.
E.g. removes shell escape codes for colours, or deletes long outputs from
the compiler if we don't need them.

Parsing the outputs
-------------------
Use `./parse.py --path PATH_TO_XFSPROGS REVISION` or see `--help` for other
options.
