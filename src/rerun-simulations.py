#!/usr/bin/python
import sys, os
if sys.version_info < (3, 0):
    import commands as subprocess
else:
    import subprocess

from GenerationTools import GenerationFileParser


def extractEnvFromRunFile(env_name):
    try:
        lines = open("setup.sh", "r").readlines()
    except IOError:
        print("No setup.sh found to extract environment variable " + env_name)
        print("Please rerun after exporting " + env_name)
        sys.exit(-1)
    else:
        for line in lines:
            if line.startswith("export " + env_name):
                value = line.split("=")[1]
                value = value.lstrip().rstrip()
                if value.find("`pwd`") is not -1:
                    value = value.replace("`pwd`", os.getcwd())
                return value

        print("No environment variable " + env_name + " found in setup.sh!")
        print("Please rerun after exporting " + env_name)
        sys.exit(-1)


# reruns all simulations for a particular generation
if __name__ == "__main__":

    filename = ""
    id = 0
    if not sys.argv[1]:
        print("must specify generation file: rerun-simulations.py filename id")
    else:
        filename = sys.argv[1]

    if not sys.argv[2]:
        print("must specify ID: rerun-simulations.py filename id")
    else:
        id = sys.argv[2]

    if os.getenv("FIELDMAPS") is None:
        os.environ["FIELDMAPS"] = extractEnvFromRunFile("FIELDMAPS") + "/"
        print("export FIELDMAPS=" + os.environ["FIELDMAPS"])

    if os.getenv("TEMPLATES") is None:
        os.environ["TEMPLATES"] = extractEnvFromRunFile("TEMPLATES") + "/"
        print("export TEMPLATES=" + os.environ["TEMPLATES"])

    env = os.getenv("OPAL_EXE_PATH")
    if env is None:
        print("Please export OPAL_EXE_PATH!")
        sys.exit(-1)

    run_opal_path = os.getenv("RUN_OPAL_EXE_PATH")
    if run_opal_path is None:
        print("Please export RUN_OPAL_EXE_PATH!")
        sys.exit(-1)


    p = GenerationFileParser(filename,id)

    run_opal  = "python " + run_opal_path + "/runOPAL.py"
#    run_opal += " --keep
#    run_opal += " --test "
    run_opal += " " + p.rows()
    print(subprocess.getoutput(run_opal))

