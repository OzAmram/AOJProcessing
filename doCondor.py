#!/usr/bin/env python

# doCondor.py #############################################################################
# Python driver for submitting condor jobs 
# Oz Amram


# ------------------------------------------------------------------------------------


import subprocess
import sys, os, fnmatch
from optparse import OptionParser
from optparse import OptionGroup
from numpy import arange
from itertools import product
import argparse
import re

default_args = []

# Options

def condor_options():

    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--outdir", default='condor_jobs/',
            help="output for analyzer. This will always be the output for job scripts.")
    parser.add_argument("-n", "--name", default='', 
            help="Name of job. Will be used for eos output and local directory")
    parser.add_argument("-v", "--verbose", dest="verbose", default=False, action="store_true", 
            help="Spit out more info")
    parser.add_argument("-i", "--input", default=[], help="Additional list of files to be used as input (comma separated)")
    parser.add_argument("--job_list", default=[], help="Idxs to actually sub")
    # Make condor submission scripts arguments
    parser.add_argument("--njobs", dest="nJobs", type=int, default=0, help="Split into n jobs, will automatically produce submission scripts")
    parser.add_argument("-s", "--script", dest="script", default="scripts/my_script.sh",
            help="sh script to be run by jobs (if splitting, should take eosoutput, nJobs and iJob as args)")
    parser.add_argument("--dry-run", dest="dryRun", default=False, action="store_true", 
            help="Do nothing, just create jobs if requested")

    # Monitor arguments (submit,check,resubmit failed)  -- just pass outodir as usual but this time pass --monitor sub --monitor check or --monitor resub
    parser.add_argument("--sub", default=False, action="store_true", help="Submit jobs")
    parser.add_argument("--resub", default=False, action="store_true", help="Re submit failed job")

    parser.add_argument("-e", "--haddEOS", dest='haddEOS', default = False, action='store_true',  help="Hadd EOS files together and save in output_files/YEAR directory")
    parser.add_argument("-g", "--getEOS", default = False, action='store_true',  help="Get EOS files and save to out directory")
    parser.add_argument("-y", "--year", dest='year', type=int, default = 2016,  help="Year for output file location")

    parser.add_argument("--tar", dest='tar', default = False, action='store_true',  help="Create tarball of current directory")
    parser.add_argument("--tarname", dest='tarname', default = "OPENDATA_CMSSW.tgz", help="Name of directory to tar (relative to cmssw_base)")
    parser.add_argument("--tarexclude", dest='tarexclude', default = '', 
            help="Name of directories to exclude from the tar (relative to cmssw_base), format as comma separated string (eg 'dir1, dir2') ")
    parser.add_argument("--cmssw", default = False, action="store_true",  help="Use full CMSSW tarball")
    parser.add_argument("--case", default = False, action="store_true",  help="Shortcut to create tarball for case  analysis")
    parser.add_argument("--root_files", dest='root_files', default = False, action="store_true",  help="Shortcut to create tarball for root files of AFB analysis")
    parser.add_argument("--no_rename", default = False, action="store_true",  help="Don't rename files for storing on EOS")
    parser.add_argument("--mem", default = 0, type=int,  help="Request extra memory")
    parser.add_argument("--overwrite", default = False, action='store_true',  help="Overwrite output dir instead of making new one (+x to name)")
    return parser



def doCondor(options):
    cwd = os.getcwd()
    #if len(args) < 1 and (not options.monitor or not options.tar) : sys.exit('Error -- must specify ANALYZER')
    cmssw_ver = os.getenv('CMSSW_VERSION', 'CMSSW_10_6_30')
    xrd_base = 'root://cmseos.fnal.gov/'
    EOS_home = '/store/user/oamram/'
    EOS_base = xrd_base + EOS_home
    EOS_base_local = "/eos/uscms/store/user/oamram/"
    scram_arch = 'slc7_amd64_gcc700'
    cmssw_name = 'CMSSW_10_6_30'

    # write job
    def write_job(out, name, nJobs, iJob, eosout='', tarname = ''):
        #print 'job_i %i nfiles %i subjobi %i'%(i,n,j)
        cwd = os.getcwd()
        eos_an_file = EOS_base + 'Condor_inputs/' + options.tarname + '.tgz'
        eos_cmssw_file = EOS_base + 'Condor_inputs/' + tarname

        sub_file = open('%s/%s_job%d.sh' % (out, name, iJob), 'w')
        sub_file.write('#!/bin/bash\n')
        sub_file.write('# Job Number %d, of %d \n' % (iJob, nJobs))
        sub_file.write('set -x \n')
        sub_file.write('source /cvmfs/cms.cern.ch/cmsset_default.sh\n')
        sub_file.write('pwd\n')
        sub_file.write('export SCRAM_ARCH=%s\n' % scram_arch)

        sub_file.write('xrdcp %s CASE_ALT_CMSSW.tgz \n' % eos_cmssw_file) 
        sub_file.write('cat my_script.sh \n')
        sub_file.write('tar -xzf CASE_ALT_CMSSW.tgz \n')
        sub_file.write('ls \n')
        sub_file.write('mv my_script.sh %s/src/ \n' % cmssw_name)
        sub_file.write('cd %s/src \n' % cmssw_name)
        sub_file.write('ls \n')
        sub_file.write('eval `scramv1 runtime -sh`\n')
        sub_file.write('scram b ProjectRename \n')
        sub_file.write('scram b -j \n')

        sub_file.write('./my_script.sh %s %i \n' % (eosout,iJob))
        sub_file.write('cd ${_CONDOR_SCRATCH_DIR} \n')
        sub_file.write('rm -rf %s\n' % cmssw_name)
        sub_file.close()
        os.system('chmod +x %s' % os.path.abspath(sub_file.name))

    # write condor submission script

    def resubmit_jobs(lofjobs):
        for sub_file in lofjobs:
            os.system('mv %s.jdl.stdout %s.jdl.v1_stdout ' % (sub_file, sub_file))
            os.system('mv %s.jdl.log %s.jdl.v1_log' % (sub_file, sub_file))
            condor_fname = os.path.abspath("%s.jdl" % sub_file)
            if(options.mem > 0. ):
                condor_file = open('%s.jdl' % sub_file, 'a')
                condor_file.write('request_memory = %i \n' % options.mem)
                condor_file.close()

            os.system("condor_submit %s " % condor_fname)


    def submit_jobs(lofjobs):
        script_location = os.path.abspath(options.outdir + options.name + "/my_script.sh")
        for sub_file in lofjobs:
            #os.system('rm -f %s.stdout' % sub_file)
            #os.system('rm -f %s.stderr' % sub_file)
            #os.system('rm -f %s.log' % sub_file)
            #os.system('rm -f %s.jdl'% sub_file)
            condor_file = open('%s.jdl' % sub_file, 'w')
            condor_file.write('universe = vanilla\n')
            condor_file.write('Executable = %s\n'% sub_file)
            condor_file.write('Requirements = OpSys == "LINUX"&& (Arch != "DUMMY" )\n')
            condor_file.write('+ApptainerImage = "/cvmfs/singularity.opensciencegrid.org/cmssw/cms:rhel7" \n')
            #condor_file.write('request_disk = 500000\n') # modify these requirements depending on job
            if(options.mem > 0. ): condor_file.write('request_memory = %i \n' % options.mem)
            condor_file.write('Should_Transfer_Files = YES\n')
            input_files = "Transfer_Input_Files = %s, %s " %(script_location, sub_file)
            for f in options.input:
                input_files += " , "  + os.path.abspath(options.outdir + options.name + "/" + f.split("/")[-1]) 
            condor_file.write(input_files + "\n")
            condor_file.write('WhenToTransferOutput = ON_EXIT \n')
            condor_file.write('use_x509userproxy = true\n')
            condor_file.write('x509userproxy = $ENV(X509_USER_PROXY)\n')
            condor_file.write('Output = %s.stdout\n' % os.path.abspath(condor_file.name))
            condor_file.write('Error = %s.stdout\n' % os.path.abspath(condor_file.name))
            condor_file.write('Log = %s.log\n' % os.path.abspath(condor_file.name))
            condor_file.write('Queue 1\n')
            condor_file.close()
            os.system('chmod +x %s'% os.path.abspath(condor_file.name))
            os.system('condor_submit %s' %(os.path.abspath(condor_file.name)))




    if options.tar:
        tar_cmd = "tar" 
        excludeList = options.tarexclude.split(',')
        excludeList = ["CMSSW_10_6_30/src/H5_maker/condor_jobs/*"]

        print("tarring CMSSW")
        #tar_cmd += " --exclude='%s' " %'*.tgz' 
        tar_cmd += " --exclude='%s' " %'*.png' 
        #tar_cmd += " --exclude='%s' " %'*.root' 
        tar_cmd += " --exclude='%s' " %'*nano_mc*.root' 
        tar_cmd += " --exclude='%s' " %'*hadd*.root' 
        tar_cmd += " --exclude='%s' " %'*.h5' 
        #tar_cmd += " --exclude='%s' " %'*.h5' 
        #tar_cmd += " --exclude=PhysicsTools/"
        tar_cmd += " --exclude='%s' " %'*.git*' 
        for item in excludeList:
            #tar_cmd += " --exclude='`%s`' " % ("echo $CMSSW_BASE/src/" + item)
            tar_cmd += " --exclude='%s' " % (item)
        tar_cmd += " -zcvf %s -C %s %s" % (options.tarname, "$CMSSW_BASE/../", cmssw_name)


        print("Executing tar command %s \n" % tar_cmd)
        os.system(tar_cmd)
        cp_cmd = "xrdcp -f %s %s" %(options.tarname, EOS_base + "Condor_inputs/")
        print(cp_cmd)
        os.system(cp_cmd)
        rm_cmd = "rm %s" %(options.tarname)
        os.system(rm_cmd)
        sys.exit("Finished tarring")

    elif (options.haddEOS):
        if(options.outdir != "condor_jobs/"): o_dir = options.outdir
        else: o_dir = "output_files/" + str(options.year) + "/" 
        hadd_cmd = "hadd -f " + o_dir + options.name + ".root"
        xrdfsls = "xrdfs root://cmseos.fnal.gov ls"
        hadd_cmd += " `%s -u %s | grep '.root' `" %(xrdfsls, EOS_home + 'Condor_outputs/' + options.name)
        print("Going to execute cmd %s: " % hadd_cmd)
        os.system(hadd_cmd)

    elif (options.getEOS):
        print("Getting files and outputting to %s" % options.outdir)
        result = subprocess.check_output(["./../condor/get_crab_file_list.sh", EOS_home + 'Condor_outputs/' + options.name]).decode("utf-8")
        print(result)
        for f in result.splitlines():
            cmd = "xrdcp  -f %s %s" % (f, options.outdir)
            #print "Going to execute cmd %s: " % cmd
            os.system(cmd)



    elif options.nJobs > 0:
    # -- MAIN
        if(options.name == ""): sys.exit("ERROR: MUST PROVIDE JOB NAME \n")
        if(options.overwrite):
            if(os.path.exists(options.outdir + options.name)):
                os.system("rm -r " + options.outdir + options.name)
        else:
            while(os.path.exists(options.outdir + options.name) and len(os.listdir(options.outdir + options.name)) != 0):
                print("Directory %s exists, adding an x" % options.outdir + options.name)
                options.name += "x"
                #os.system('rm -r %s' % (options.outdir + options.name))
        print("Dir is %s" %( options.outdir + options.name))
        eos_dir_name = EOS_base + 'Condor_outputs/' + options.name
        #os.system("eosrm -r %s" % eos_dir_name)
        os.system('mkdir -p %s' % (options.outdir + options.name))
        os.system('cp %s %s/my_script.sh' %(options.script, options.outdir + options.name))
        for f in options.input:
            os.system('cp %s %s/' %(f, options.outdir + options.name))

        os.system('chmod +x %s/my_script.sh' % (options.outdir + options.name))

        for iJob in range(options.nJobs):
            if(len(options.job_list) == 0 or iJob in options.job_list):
                eos_file_name = EOS_base + 'Condor_outputs/' + options.name + '/'
                write_job(options.outdir + options.name, options.name, options.nJobs, iJob, eos_file_name, tarname = options.tarname)

    # submit jobs by looping over job scripts in output dir
    if options.resub:

        odir = options.outdir + options.name + "/"
        # pick up job scripts in output directory (ends in .sh)
        lofjobs = []

        eos_out_dir = EOS_base_local + 'Condor_outputs/' + options.name + '/'

        
        finished_jobs = []
        for f_out in os.listdir(eos_out_dir):
            if('.h5' in f_out): f_out = f_out.replace(".h5", "")
            nums = [int(num) for num in re.findall(r"\d+", f_out)]
            if(len(nums) == 0): continue
            else:
                jobNum = nums[-1]
                finished_jobs.append(jobNum)

        for root, dirs, files in os.walk(odir):
            for f in fnmatch.filter(files, '%s_*.sh' %options.name):
                #lofjobs.append('%s/%s' % (os.path.abspath(root), f))
                nums = [int(num) for num in re.findall(r"\d+", f)]
                if(len(nums) == 0): continue
                else:
                    jobNum = nums[-1]
                    if(jobNum not in finished_jobs):
                        print(odir+ f, jobNum)
                        lofjobs.append(odir + f)




        print('Resubmitting %d jobs from directory %s' % (len(lofjobs), odir))
        resubmit_jobs(lofjobs)
        print("Finished submitting")
        return
    # submit jobs by looping over job scripts in output dir
    elif options.sub:
        odir = options.outdir + options.name

        # pick up job scripts in output directory (ends in .sh)
        os.system('xrdfs %s mkdir %s' % (xrd_base, EOS_home + 'Condor_outputs/' + options.name))
        lofjobs = []
        for root, dirs, files in os.walk(odir):
            for f in fnmatch.filter(files, '%s_*.sh' %options.name):
                lofjobs.append('%s/%s' % (os.path.abspath(root), f))
        print('Submitting %d jobs from directory %s' % (len(lofjobs), odir))
        submit_jobs(lofjobs)
        print("Finished submitting")
        return

if __name__ == "__main__":
    parser = condor_options()
    options = parser.parse_args()
    doCondor(options)
