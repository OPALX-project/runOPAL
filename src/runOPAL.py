#!/usr/bin/env python

"""
Script that launches OPAL simulations

@author: Andreas Adelmann <andreas.adelmann@psi.ch>
@author: Yves Ineichen
@version: 0.1

"""

import sys,os,shutil,glob
import subprocess
from simulation import Simulation
from opaldict import OpalDict


def getPaths(path, pattern, name):
    result = glob.glob(os.path.join(path,pattern))
    if not result:
        print('No '+name+' file ('+pattern+') found')
        sys.exit()
    return result


def getBaseName(inputfilePath):
    templates = getPaths(inputfilePath, '*.tmpl', 'template')
    
    name = templates[0].split('/')[-1][:-5] #NOTE: choose first (alphanumeric order) *.tmpl file by default
    if os.path.isfile(os.path.join('.',name+'.data')):
        return name
    
    print('Template and data filename do not match, '+name+'.data expected')
    sys.exit()


def printUsage():
    print("./runOPAL.py [--help] [--filename=str] [--test] [--quiet] [--info=num] [--test] [--keep] [--queue=qname] [--hypert=num] [--nobatch] [ATTR=SCANVALUE] {[ATTR=VALUE]}")
    print("")
    print("--help                prints this message")
    print("--filename | -f=<str> sets base file name for both *.data and *.tmpl")
    print("--test | -t           does everything but submitting the job")
    print("--keep | -k           if same simulation has been run before, keep old data and abort")
    print("--nobatch             run OPAL locally not using the batch system and waits until the job is done")
    print("--noopt               ignore optimization template (if any) and perform regular simulation")
    print("--quiet               suppress debug printout")
    print("--info | -i=<num>     steers the std-output of OPAL. The range is 0 < num < 6 (default), from minimal to maximum output")
    print("--queue=<qname> defines in which queue the job goes. Overwrites QUEUE (deprecated SGE_QUEUE)")
    print("--hypert=<num>  defines the number of Hyper-Threads used. Default 0")
    print("")
    print("SCANVALUE=start:end:step, scans a parameter space, e.g. example TFWHM=0.85:0.90:0.01 ")
    print("ATTR refers to a name in the data file")
    print("")
    print("Recognized environment variables: DISTRIBUTIONS, FIELDMAPS, OPTIMIZER, OPAL_EXE_PATH, TEMPLATES, QUEUE, RAM, TIME (deprecated SGE_)")
    # temporary see issue #8
    print("")
    print("Important: runOPAL is currently not compatible with the command SAMPLE")


def checkCompat(tmplFile, incompatible): #NOTE: SAMPLE command not compatible with runOPAL (issue #8)
    templateFile = open(tmplFile,'r')
    for line in templateFile:
        if line.startswith('//'):
            continue
        if any(command in line for command in incompatible):
            print(', '.join(incompatible)+' command(s) currently not compatible with runOPAL')
            sys.exit()
    templateFile.close()


def traverseRanges(list, opaldict, args, doNobatch):
    """
    Traverse all possible combinations of range variable values. Start simulation
    once all range variables are fixed to a value. A list entry has the following
    structure:
    ['name of var', start_value, end_value, step_value]
    """
    head = list[0]
    tail = list[1:]
    curval = head[1][0]
    endval = head[1][1]
    step   = head[1][2]
    qid = -1
    if curval > endval:
        print('range is empty, start value',curval,'needs to be higher than end value',endval)
    while curval <= endval:
            opaldict[head[0]] = curval
            if len(tail) == 0:
                #run simulation
                sim = Simulation(opaldict)
                qid = sim.run(*args)
                if doNobatch:
                    print("... finished!\n")
                else:
                    print("SGE-ID= {}\n".format(qid))
            else:
                traverseRanges(tail, opaldict, args, doNobatch)
            curval = curval + step
 

def main(argv):
    """
    main method
    """
    N = -1               # a running number; if given use it to label directory!
    quiet  = False
    doTest = False
    doKeep = False
    doNobatch = False
    doOptimize = True    #NOTE: this flag is opposite of --noopt 
    queue = ""
    info = 6
    hypert = 0 
    qid = -1
    
    inputfilePath = None
    baseFileName = None
    
    for arg in argv:
        if arg.startswith("--help"):
            printUsage()
            exit()
        elif arg.startswith("--filename") or arg.startswith("-f"):
            baseFileName = arg.split("=")[1]
        elif arg.startswith("--test") or arg.startswith("-t"):
            doTest = True
        elif arg.startswith("--keep") or arg.startswith("-k"):
            doKeep = True
        elif arg.startswith("--nobatch"):
            doNobatch = True
        elif arg.startswith("--noopt"):
            doOptimize = False
        elif arg.startswith("--quiet"):
            quiet = True
        elif arg.startswith("--info") or arg.startswith("-i"):
            info = arg.split("=")[1]
        elif arg.startswith("--queue"):
            queue = arg.split("=")[1]
        elif arg.startswith("--hypert"):
            hypert = int(arg.split("=")[1])
        elif arg.startswith("-"):
            print(arg,'is not a valid option, see --help for the available options')
            exit()

    # safety check
    if os.getcwd() == os.environ.get('TEMPLATES') or os.getcwd() == os.environ.get('OPTIMIZER'):
        print('Working directory is the same as the TEMPLATES or OPTIMIZER directory! This is not allowed... bye!')
        sys.exit()
    
    # determine what kind of job should be ran, simulation by default
    if doOptimize and os.environ.get('OPTIMIZER'):
        if quiet == False:
            print('job type: OPTIMIZATION')
        inputfilePath = os.environ.get('OPTIMIZER')
    if not (inputfilePath and glob.glob(os.path.join(inputfilePath,'*.tmpl'))):
        if quiet == False:
            print('job type: SIMULATION')
        doOptimize = False
        if os.environ.get('TEMPLATES'):
            inputfilePath = os.environ.get('TEMPLATES')
        elif (glob.glob(os.path.join('.','*.tmpl'))):
            inputfilePath = '../'
        else:
            print('Template file unknown -> exiting ...')
            sys.exit()
    
    #check that tmpl and data files can be found or guessed
    if not baseFileName:
        baseFileName = getBaseName(inputfilePath)
    elif not os.path.isfile(os.path.join(inputfilePath,baseFileName+'.tmpl')):
        print(baseFileName+'.tmpl cannot be found! Check if it exists in '+inputfilePath)
        sys.exit()
    if quiet == False:
        print('baseFileName = '+baseFileName)
    
    dataFile = baseFileName + '.data'
    tmplFile = os.path.join(inputfilePath,baseFileName+'.tmpl')
    oinpFile = baseFileName + '.in' # the resulting OPAL input file
    
    checkCompat(tmplFile, ['SAMPLE']) # check compatibility
    
    #create the dictionary
    opaldict = OpalDict(dataFile)
    # check if template values must be changed
    # if so add update the dictionary with the default values
    opaldict.addUserValues(argv)
    opaldict.scale()

    if not opaldict.hasRanges():
        sim = Simulation(opaldict)
        qid = sim.run(N, baseFileName, inputfilePath, tmplFile, oinpFile, doTest, doKeep, doNobatch, doOptimize, info, queue, hypert, quiet)
        if doNobatch:
            if quiet == False:
                print( "... finished!\n")
        #else:
        #    print( "SGE-ID= {}\n".format(qid))
    else:
        ranges = opaldict.Range()

        #create range toplevel dir
        dirname = baseFileName
        for p in opaldict.uservars:
            dirname += "_" + str(p[0]) + "=" + str(p[1])
        for (k, v) in ranges.items():
            dirname += "_" + k + "=" + str(v[0]) + ":" + str(v[1]) + ":" + str(v[2])
        # If there's already a directory remove it...
        if os.path.isdir(dirname):
            if doKeep:
                print( 'KEEP existing directory ', dirname)
            else:
                print( 'REMOVE existing directory', dirname)
                shutil.rmtree(dirname)
                # create directory and change to the directory
                os.mkdir(dirname)
        else:
            os.mkdir(dirname)
            
        os.chdir(dirname)

        print(ranges)
        #run simulations of all possible combinations
        args = [N, baseFileName, inputfilePath, tmplFile, oinpFile, doTest, doKeep, doNobatch, doOptimize, info, queue, hypert, quiet]
        traverseRanges(list(ranges.items()), opaldict, args, doNobatch)
        
        # clean up
        os.system("rm -f *.bak ")
        os.chdir("..")
        

#call main
if __name__ == "__main__":
    main(sys.argv[1:])
