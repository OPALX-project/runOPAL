"""
Simulation class handles batch job related things

@author: Andreas Adelmann <andreas.adelmann@psi.ch>
@author: Yves Ineichen
@version: 0.1
"""

import sys,os,shutil, subprocess
#import numpy as np


### Helper methods
def isInDirectory(filepath, directory):
    # From https://stackoverflow.com/questions/3812849/how-to-check-whether-a-directory-is-a-sub-directory-of-another-directory
    ''' Check if filepath is inside directory '''
    return os.path.realpath(filepath).startswith(os.path.realpath(directory) + os.sep)

def linkDirectory(path, name=''):
    '''Make files available in working directory with recursive symbolic links'''
    # Check for recursiveness
    if isInDirectory(os.getcwd(),path):
        print (name + ' directory is subdirectory of working directory! runOPAL cannot handle this.. bye!')
        sys.exit()
    # lndir and if fails try cp
    if os.system('lndir '+path) != 0:
        print("lndir failed (possibly doesn't exist on this system), using cp -rs... \n"),
        if os.listdir(path):
            os.system('cp -rs '+path+'/* .')

def linkFile(path, name):
    '''Make a file available in working directory with a symbolic link'''
    path = os.path.join(path,name)
    if not os.path.isfile(path):
        print (name+' cannot be found')
        sys.exit()
    os.system('ln -s '+path+' .')

def extractStr(line, name):
    zero = line.find(name)
    if zero < 0:
        return None
    start = min(x for x in [line.find('"',zero ), line.find("'", zero )] if x > 0) +1
    end   = min(x for x in [line.find('"',start), line.find("'", start)] if x > 0)
    return line[start:end]


class Simulation:
    def __init__(self, opaldict):
        self.opaldict = opaldict
        self.dirname = ""

    def createDirectory(self, dirname, doKeep, quiet):
        # If there's already a directory remove it...
        if os.path.isdir(self.dirname):
            if doKeep:
                print('KEEP existing directory {}'.format(self.dirname))
                print(self.dirname)
                return False
            else:
                if quiet == False:
                    print('REMOVE existing directory {}'.format(self.dirname))
                shutil.rmtree(self.dirname)

        # create directory
        os.mkdir(self.dirname)
        return True

    def run(self,N, baseFileName, inputfilePath, tmplFile, oinpFile, doTest, doKeep, doNobatch, doOptimize, info, queue, hypert, quiet):
        # make directory name indicating changed values
        self.dirname = baseFileName
        if N >= 0:
            self.dirname += str(N)
        self.dirname += self.opaldict.generateDirectoryName()
        
        try:
            CORES = self.opaldict['CORES']
        except KeyError:
            print("CORES not set bye bye")
            sys.exit(1)

        if self.createDirectory(self.dirname, doKeep, quiet) == False:
            print( "Simulation results already exist")
            return
        os.chdir(self.dirname)
        
        # Linking magnet and RF files
        if (os.environ.get('FIELDMAPS')):
            fieldmapPath = os.environ.get('FIELDMAPS')
        else:
            fieldmapPath = '../fieldmaps'
            if not (os.path.isdir(fieldmapPath)):
                print( 'Fieldmap directory unknown exiting ...')
                sys.exit()
        linkDirectory(fieldmapPath,'Fieldmap')
        
        # Link distribution directory if present
        if (os.environ.get('DISTRIBUTIONS')):
            distributionPath = os.environ.get('DISTRIBUTIONS')
            if os.path.isdir(distributionPath):
                linkDirectory(distributionPath,'Distribution')
        
        # Read in the file
        filedata = None
        with open(tmplFile, 'r') as file :
            filedata = file.read()
        # do the replacements in the templatefile
        for s,value in self.opaldict.items():
            # Replace the target string
            filedata = filedata.replace('_'+s+'_', str(value))
        # Write the file out again
        with open(oinpFile, 'w') as file:
            file.write(filedata)
        
        #NOTE: What's the best place to link tmpl file? $TEMPLATES, _TEMPLATEDIR_, or parisng?
        if doOptimize:
            flag = False
            tmplDir = None
            tmplIn  = None
            templateFile = open(oinpFile,'r')
            for line in templateFile:
                if not line.startswith('//'):
                    if 'OPTIMIZE' in line:
                        flag = True
                    if flag and not tmplDir:
                        tmplDir = extractStr(line,'TEMPLATEDIR')
                    if flag and not tmplIn:
                        tmplIn = extractStr(line,'INPUT').split('/')[-1]
            templateFile.close()
            
            linkFile('..', tmplIn[:-5]+'.data')
            os.mkdir(tmplDir)
            os.chdir(tmplDir)
            linkFile(os.path.join('../..',tmplDir), tmplIn)
            os.chdir('..')
        
        if os.environ.get('OPAL_EXE_PATH'):
            if doNobatch:
                opalexe = os.environ.get('OPAL_EXE_PATH') + '/opal'
            else:
                opalexe = '$OPAL_EXE_PATH/opal'
        else:
            opalexe = 'opal'
        if quiet == False:
            print( 'Simulation directory is {} using OPAL at {}'.format(self.dirname, os.environ.get('OPAL_EXE_PATH')))
            print( 'Using templatefile at ' + inputfilePath)
            print( 'Using fieldmaps at    ' + fieldmapPath)
            print( 'Parameter set in ' + oinpFile + ' are:')
            for s, value in sorted(self.opaldict.items()): #EDIT: fixed indentation
                if quiet == False:
                    print( ' :::: ' + s + ' = ' + str(value))

        if not doNobatch:
            #hostname = commands.getoutput("hostname")
            hostname = (subprocess.check_output('hostname').decode('utf-8')).strip()
            if quiet == False:
                print("On host {}".format(hostname))

            if os.getenv("SGE_TIME"):
                print( "You use deprecated environment variable SGE_TIME. Please use in the future TIME")
                time = os.getenv("SGE_TIME")
            else:
                #print('You did not set a time limit. Using default: s_rt=23:59:00,h_rt=24:00:00')
                time = os.getenv("TIME", "s_rt=23:59:00,h_rt=24:00:00")

            if os.getenv("SGE_RAM"):
                print( "You use deprecated environment variable SGE_RAM. Please use in the future RAM")
                ram = os.getenv("SGE_RAM")
            else:
                ram = os.getenv("RAM", "4")

            if not queue:
                try: 
                    queue = os.environ.get('QUEUE') 
                except:
                    queue = os.getenv("SGE_QUEUE", "prime_bd.q")
            
            # Merlin6
            if (hostname.startswith("merlin-l")):
                batchsys  = 'SLURM'
                runfile   = 'run.merlin6'
                time      = os.getenv("SLURM_TIME", "24:00:00")
                ram       = os.getenv("SLURM_RAM",  "36")
                partition = os.getenv("SLURM_PARTITION", "general")
                self.WriteMerlin6(opalexe, oinpFile, CORES, time, ram, info, runfile, partition)

            # ANL theta.alcf.anl.gov
            elif (hostname.startswith("theta")):
                batchsys = 'COBALT'
                runfile  = 'run.sh'
                self.WriteTheta(opalexe, oinpFile, CORES, time, ram, info, queue, hypert)

            # ANL blues.lcrc.anl.gov
            elif (hostname.startswith("blogin")):
                batchsys = 'PBS'
                runfile  = 'run.blues'
                self.WritePBSBlues(opalexe, oinpFile, CORES, time, ram, info, queue)

            # ANL Bebop
            elif (hostname.startswith("bebop") or hostname.startswith("bdw") or hostname.startswith("knl")):
                batchsys = 'SLURM'
                runfile  = 'run.bebop'
                time     = os.environ["TIME"]
                self.WriteBebop(opalexe, oinpFile, CORES, time, ram, info, runfile, queue, hypert, quiet)

            # NERSC Cori Haswell
            elif (hostname.startswith("cori")):
                batchsys = 'SLURM'
                runfile  = 'run.cori'
                self.WriteCori(opalexe, oinpFile, CORES, time, ram, info, runfile)

            # NERSC Edison
            elif (hostname.startswith("edison")):
                batchsys = 'SLURM'
                runfile  = 'run.edison'
                self.WriteEdison(opalexe, oinpFile, CORES, time, ram, info, runfile)

            # CSCS Piz-Daint
            elif (hostname.startswith("daint")):
                batchsys = 'SLURM'
                runfile  = 'run.daint'
                time = os.getenv("SLURM_TIME", "00:01:00")
                ram  = os.getenv("SLURM_RAM", "36")
                partition = os.getenv("SLURM_PARTITION", "normal")
                account = os.getenv("SLURM_ACCOUNT", "psi07")
                self.WritePizDaint(opalexe, oinpFile, CORES, time, ram, info, runfile, partition, account)

            elif (hostname.startswith("eofe")):
                batchsys = 'SLURM'
                runfile = 'run.engaging'
                time = os.getenv("SLURM_TIME", "24:00:00")
                ram  = os.getenv("SLURM_RAM", "120")            
                self.WriteEngaging(opalexe, oinpFile, CORES, time, ram, info, runfile)

            else:
                print("Hostname not known bye bye")
                sys.exit(1)

        qid = -1

        if doTest:
            if quiet == False:
                print( 'Done with setup of the OPAL simulation but not submitting the job (--test) \n\n\n')

        elif doNobatch:
            if quiet == False:
                print( 'Done with setup of the OPAL simulation and executing the job on {} cores...\n\n\n'.format(CORES)) 
            ofn, fileExtension = os.path.splitext(oinpFile)
            if quiet == False:
                print( 'STD output is written to {}.out'.format(ofn))
            #execommand = 'mpirun -np ' + str(CORES)  + ' ' + opalexe + ' ' + oinpFile + '  2>&1 | tee ' + ofn + '.out'
            outfileName = ofn +'.out'
            # Currently not writing to screen anymore
            # There is a solution described at https://stackoverflow.com/questions/15535240/python-popen-write-to-stdout-and-log-file-simultaneously
            with open(outfileName,'w') as outfile:
                qid = subprocess.call(['mpirun', '-np', str(CORES), opalexe, oinpFile], stdout=outfile, stderr=outfile)

        else:
            if batchsys == 'SLURM' or batchsys == 'COBALT':
                if batchsys == 'SLURM':
                    command = 'sbatch'
                elif batchsys == 'COBALT':
                    command = 'qsub'

                qid = subprocess.call([command, runfile, '|', 'awk','\'{print $3}\''])
                if quiet == False:
                    print( 'Done with setup of the OPAL simulation and submitting the job with {} cores \n\n\n'.format(CORES))

            elif batchsys == 'PBS':
                if quiet == False:
                    print( 'Done with setup of the OPAL simulation, please submit the job yourself')

            else:
                print("Batch system", batchsys, "not known!")

        os.chdir('..')
        return qid
    
    
    ### Write for host
    def WriteCori(self, opalexe, oinpFile, cores, time, ram, info, name):
        title=oinpFile.partition(".")[0]
        myfile = open(name,'w')
        s1 = "#!/bin/bash -l \n"
        s1 += "#SBATCH -p regular \n"
        s1 += "#SBATCH -N 1 \n"
        s1 += "#SBATCH -t " + time + "G\n" 
        s1 += "#SBATCH -J " + title + "\n"
        s1 += "#SBATCH --qos=premium \n"
        s1 += "srun -n 1 .... \n"
        myfile.write(s1)
        myfile.close()
    
    
    def WriteEngaging(self, opalexe, oinpFile, cores, time, ram, info, name):
        print("Writing SLURM run file for Engaging cluster at MIT")
        
        cores = int(cores)
        coresPerNode = 32
        partition = os.getenv("SLURM_PARTITION", "sched_mit_psfc")
        
        if ((cores%coresPerNode) is 0):
            nodes = int(cores/coresPerNode)
        else:
            nodes = int(cores/coresPerNode) + 1

        with open(name, 'w') as outfile:
            outfile.write("#!/bin/bash\n" 
                          "# submit with sbatch {}\n"
                          "# commandline arguments may instead by supplied with #SBATCH <flag> <value>\n"
                          "# commandline arguments override these values\n"
                          "\n"
                          "# Number of nodes\n".format(name))
            outfile.write("#SBATCH -N {}\n".format(nodes))
            outfile.write("# Number of total processor cores \n")
            outfile.write("#SBATCH -n {}\n".format(cores))
            outfile.write("# Memory (MB) \n")
            outfile.write("#SBATCH --mem {}\n".format(int(ram) * 1000))
            outfile.write("# specify how long your job needs.\n")
            outfile.write("#SBATCH --time={}\n".format(time))
            outfile.write("# which partition or queue the jobs runs in\n")
            outfile.write("#SBATCH -p {}\n".format(partition))
            outfile.write("#customize the name of the stderr/stdout file. %j is the job number\n")
            outfile.write("#SBATCH -o {}.o%j".format(os.path.splitext(oinpFile)[0]))
            outfile.write("\n")
#            outfile.write("#load default system modules\n")
#            outfile.write(". /etc/profile.d/modules.sh")
#            outfile.write("\n")
#            outfile.write("#load modules your job depends on.\n")
#            outfile.write("#better here than in your $HOME/.bashrc to make "
#                         "debugging and requirements easier to track.\n")
#            outfile.write("module load gcc/4.8.4\n")
#            outfile.write("module load engaging/openmpi/1.8.8\n")
#            outfile.write("module load engaging/cmake/3.5.2\n")
#            outfile.write("module load engaging/boost/1.56.0\n")
#            outfile.write("module load engaging/gsl/2.2.1\n")
#            outfile.write("\n")
            outfile.write("####################################################\n")
            outfile.write("# BEGIN DEBUG\n")
            outfile.write("# Print the SLURM environment on master host: \n")
            outfile.write("####################################################\n")
            outfile.write("echo '=== Slurm job  JOB_NAME=$JOB_NAME  JOB_ID=$JOB_ID'\n") 
            outfile.write("####################################################\n")
            outfile.write("echo DATE=`date`\n")
            outfile.write("echo HOSTNAME=`hostname`\n") 
            outfile.write("echo PWD=`pwd`\n")
            outfile.write("####################################################\n")
            outfile.write("echo 'Running environment:' \n")
            outfile.write("env \n")
            outfile.write("####################################################\n")
            outfile.write("echo 'Loaded environment modules:' \n")
            outfile.write("module list 2>&1\n") 
            outfile.write("echo \n")
            outfile.write("# END DEBUG\n") 
            outfile.write("####################################################\n")
            outfile.write("\n")
            outfile.write("#Finally, the command to execute.\n")
            outfile.write("#The job starts in the directory it was submitted from.\n")
            outfile.write("#Note that mpirun knows from SLURM how many processor we have\n")
            outfile.write("mpirun {} {} --info {} --warn 6\n".format(opalexe, oinpFile, info))
    
    
    def WriteEdison(self, opalexe, oinpFile, cores, time, ram, info, name):
        title=oinpFile.partition(".")[0]
        
        coresPerNode = 24
        cores = int(cores)
        
        if cores % coresPerNode == 0:
            nodes = int(cores / coresPerNode)
        else:
            nodes = int(cores / coresPerNode) + 1
        
        s1 = "#!/bin/bash -l \n"
        s1 += "#SBATCH -q regular \n"
        s1 += "#SBATCH -N " + str(nodes) + " \n"
        s1 += "#SBATCH -t " + time + "\n" 
        s1 += "#SBATCH -J " + title + "\n"
        s1 += "#SBATCH -o " + title + ".o%j\n"
        s1 += "#SBATCH -L SCRATCH \n"
        s1 += "srun -n " + str(cores) + " " + opalexe + " " + oinpFile + "\n"

        myfile = open(name, 'w')
        myfile.write(s1)
        myfile.close()
        
    def WriteMerlin6(self, opalexe, oinpFile, cores, time, ram, info, name, partition):
        # ADA this is for the new PSI Merlin6     
        title = oinpFile.partition(".")[0]
        myfile = open(name, 'w')
        s1 =  "#!/bin/bash -l \n"
        s1 += "#SBATCH --job-name=" + title + "\n"
        s1 += "#SBATCH --output="   + title + ".o%j\n"
        s1 += "#SBATCH --time=" + time + "\n"
        s1 += "#SBATCH --ntasks=" + str(cores) + "\n"
        s1 += "#SBATCH --ntasks-per-core=1 \n"
        # s1 += "#SBATCH --constraint=mc \n"
        # Discussed in https://gitlab.psi.ch/OPAL/runOPAL/issues/7:
        #if (int(cores) > 22):
        #    s1 += "#SBATCH --ntasks-per-node=16 \n"
        #else:
        #    s1 += "#SBATCH --nodes=1 \n"
        s1 += "#SBATCH --partition=" + str(partition) + " \n"
        # s1 += "#SBATCH --exclude=merlin-c-001 \n"
        s1 += "#SBATCH --cores-per-socket=22 \n"
        s1 += "#SBATCH --sockets-per-node=2 \n"
        s1 += "mpirun " + opalexe + " " + oinpFile + " --info " + str(info) + "\n"
        myfile.write(s1)
        myfile.close()

    def WritePizDaint(self, opalexe, oinpFile, cores, time, ram, info, name, partition, account):
        # XC40 Compute Nodes
        # Intel Xeon E5-2696 v4 @ 2.10GHz (2x18 cores, 64/128 GB RAM)
        # http://user.cscs.ch/computing_systems/piz_daint/index.html
        coresPerNode = 36
        title = oinpFile.partition(".")[0]
        myfile = open(name, 'w')
        s1 =  "#!/bin/bash -l \n"
        s1 += "#SBATCH --job-name=" + title + "\n"
        s1 += "#SBATCH --time=" + time + "\n"
        s1 += "#SBATCH --ntasks=" + str(cores) + "\n"
        s1 += "#SBATCH --ntasks-per-node=" + str(coresPerNode) + " \n"
        s1 += "#SBATCH --ntasks-per-core=1 \n"
        s1 += "#SBATCH --cpus-per-task=1 \n"
        s1 += "#SBATCH --constraint=mc \n"
        s1 += "#SBATCH --mem=" + str(ram) + "GB \n"
        s1 += "#SBATCH --partition=" + str(partition) + " \n"
        s1 += "#SBATCH --account=" + str(account) + " \n"
        s1 += "export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK \n"
        s1 += "module load daint-mc \n"
        s1 += "srun " + opalexe + " " + oinpFile + "\n"
        myfile.write(s1)
        myfile.close()
    
    
    def WritePBSBlues(self, opalexe, oinpFile, cores, time, ram, info, queue):
        # time  <- export SGE_TIME="walltime=0:20:00"
        # cores <- export CORES="nodes=1:ppn=16"
        title=oinpFile.partition(".")[0]
        myfile = open('run.pbs','w')
        s1 = "#!/bin/sh \n"
        s1 += "#PBS -o " + title + "_log  \n"
        s1 += "#PBS -r n \n"
        s1 += "#PBS -j oe \n"
        s1 += "#PBS -N " + title + "\n"
        s1 += "#PBS -m aeb \n"
        s1 += "#PBS -M nneveu@anl.gov \n"
        s1 += "#PBS -l " + time + " \n"
        s1 += "#PBS -l " + cores + " \n"
        s1 += "#PBS -q " + queue + " \n"
        try:
            v = os.environ["OPAL_EXE_PATH"]
        except KeyError:
            print("OPAL_EXE_PATH not set bye bye")
            sys.exit(1)
        s1 += "cd $PBS_O_WORKDIR \n"
        s1 += "####################################################\n"
        s1 += "echo DATE=`date`\n"
        s1 += "echo HOSTNAME=`hostname` \n"
        s1 += "echo PWD=`pwd`\n"
        s1 += "cat $PBS_NODEFILE\n"
        s1 += "NSLOTS=$(wc -l < $PBS_NODEFILE)\n"
        s1 += "####################################################\n"
        s1 += "CMD=$OPAL_EXE_PATH/opal \n"
        s1 += "echo $CMD\n"
        s1 += "ARGS=" + "\"" + oinpFile + " --info " + str(info) + " --warn 6 \"\n"
        s1 += "####################################################\n"
        s1 += "MPICMD=\"mpirun -np $NSLOTS $CMD $ARGS\" \n"
        s1 += "echo $MPICMD\n"
        s1 += "$MPICMD \n"
        s1 += "####################################################\n"
        myfile.write(s1)
        myfile.close()              
    
    
    def WriteBebop(self, opalexe, oinpFile, cores, time, ram, info, name, queue, hypert, quiet):
        # BDW and KNL Compute Nodes at ANL
        # http://www.lcrc.anl.gov/for-users/using-lcrc/running-jobs/running-jobs-on-bebop/
        if type(cores) is str:
            cores = int(cores)
        else:
            cores = int(cores)
        #Checking that a valid queue is selected
        #Adjusting number of cores for specified queue 
        if (queue=='bdw' or queue=='bdwall' or queue=='bdwd'):
            if quiet == False:
                print('Running on BDW') 
            coresPerNode = 36 * (hypert+1)     # hypert == 0 -> no hyper threading 
        elif (queue=='knl' or queue=='knlall' or queue=='knld'):
            if quiet == False:
                print('Running on KNL')
            coresPerNode = 64 * (hypert+1)
        else:
            print('You have picked a non-valid queue!! Your run will fail!!')

        #Calculating # of nodes needed, and # of tasks per node 
        #  Only calc tasks per node if total core number 
        #  is not evenly divisible by # of nodes
        if (cores % coresPerNode) is 0:
            if (cores < coresPerNode):
                nodes = 1
            else:
                nodes = cores / coresPerNode
                tasks_per_node = cores/nodes
        else:
            while((cores % coresPerNode) != 0): 
                coresPerNode -= 1
                nodes = cores/coresPerNode 

            tasks_per_node = cores/nodes
            #print(nodes,cores, tasks_per_node)

        title = oinpFile.partition(".")[0]
        myfile = open(name, 'w')
        
        s1 =  "#!/bin/bash -l \n"
        s1 += "#SBATCH --job-name=" + title + "\n"
        s1 += "#SBATCH -o " + title + ".%j.%N.out \n" 
        s1 += "#SBATCH -e " + title + ".%j.%N.error \n"
        s1 += "#SBATCH -p " + queue + " \n"
        s1 += "#SBATCH --time=" + time + "\n"
        s1 += "#SBATCH --ntasks=" + str(cores) + "\n"
        s1 += "#SBATCH --ntasks-per-node=" + str(coresPerNode) + "\n"
        s1 += "cd $SLURM_SUBMIT_DIR \n"
        #s1 += "export I_MPI_SLURM_EXT=0 \n"
        s1 += "export I_MPI_FABRICS=shm:tmi \n"
        if (queue=='knl' or queue=='knlall' or queue=='knld'):
            s1 += "#SBATCH -C knl,quad,cache \n"
        if int(nodes) > 1:
            s1 += "#SBATCH --ntasks-per-node=" + str(tasks_per_node) + " \n"
            s1 += "mpirun -n $SLURM_NTASKS "+ opalexe + " " + oinpFile + "\n"
        else:
            s1 += "mpirun -n $SLURM_NTASKS " + opalexe + " " + oinpFile + "\n"
        #s1 += "#SBATCH --mem=" + ram + "GB \n"
        #s1 += "export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK \n"
        #s1 += "--hint=nomultithread " + opalexe + " " + oinpFile + "\n"
       
        myfile.write(s1)
    
    
    def WriteTheta(self, opalexe, oinpFile, cores, time, ram, info, queue, hypert):
        # queue = default, debug-cache-quad, debug-flat-quad
        # cores = min of 8 nodes for default queue 
        try:
            v = os.environ["OPAL_EXE_PATH"]
        except KeyError:
            print("OPAL_EXE_PATH not set bye bye")
            sys.exit(1)
              
        cores        = int(cores)
        coresPerNode = 64 * (hypert+1)

        if (cores % coresPerNode) is 0:
            if (cores < coresPerNode):
                nodes = int(1)
            else:
                nodes = int(cores / coresPerNode)
                tasks_per_node = int(cores/nodes)
        else:
            while((cores % coresPerNode) != 0): 
                coresPerNode -= int(1)
                nodes = int(cores/coresPerNode) 

            tasks_per_node = cores/nodes
            #print(nodes,cores, tasks_per_node)
   
        if cores < 512:
            queue = 'debug-cache-quad'
            time  = '00:59:00'
        #elif cores > 512: 
        #nodes = np.ceil(cores/64)

        total_mpi_ranks = int(nodes*coresPerNode)

        title=oinpFile.partition(".")[0]
        myfile = open('run.sh','w')
        s1 =  "#!/bin/bash  \n"
        s1 += "#COBALT -t " + time + " \n"
        s1 += "#COBALT -n " + str(nodes) + " \n"
        s1 += "#COBALT -q " + queue + " \n"
        s1 += "#COBALT --attrs mcdram=cache:numa=quad \n"
        s1 += "#COBALT -A awa \n"
        s1 += 'echo "Starting Cobalt job script"\n'
        s1 += "export n_nodes=$COBALT_JOBSIZE \n"
        s1 += "export n_mpi_ranks_per_node=" + str(coresPerNode)+ " \n"
        s1 += "export n_mpi_ranks=" + str(total_mpi_ranks) + "\n"
        #s1 += "export n_openmp_threads_per_rank=4"
        if hypert > 0:       
            s1 += "export n_hyperthreads_per_core=2 \n"
        #s1 += "export n_hyperthreads_skipped_between_ranks=4"
        s1 += "####################################################\n"
        s1 += "ARGS=" + "\"" + oinpFile + " --info " + str(info) + " --warn 6 \"\n"
        s1 += "CMD=$OPAL_EXE_PATH/opal \n"
        if hypert > 0:
            s1 += "MPICMD=\"aprun -n $n_mpi_ranks -N $n_mpi_ranks_per_node -j $n_hyperthreads_per_core $CMD $ARGS\" \n"
        else:
            s1 += "MPICMD=\"aprun -n $n_mpi_ranks -N $n_mpi_ranks_per_node $CMD $ARGS\" \n"
        s1 += "echo $MPICMD\n"
        s1 += "$MPICMD \n"
        s1 += "####################################################\n"
        myfile.write(s1)
        myfile.close()              
        os.chmod("run.sh", 0o775)

