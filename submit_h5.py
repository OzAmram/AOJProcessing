import sys, os

def print_and_do(s):
    print(s)
    return os.system(s)



eos_base = "root://cmseos.fnal.gov/"

#label = "2016H"
#nJobs = 1309
#label = "2016G"
#nJobs = 1236
#label = "QCDPt300"
#nJobs = 1087
label = "QCDPt800"
nJobs = 834
#label = "Zprime_PSweight"
#nJobs = 10
mc = True
mem = 6000.



if(nJobs > 0):
    oname = label + "_job${2}.h5"
else:
    oname = label + ".h5"

script_name = "scripts/script_temp.sh"
print_and_do("cp scripts/h5_template.sh %s" % script_name)
f = open(script_name, "a")

if(not mc):
    cmd_PFNano = "cmsRun pfnano_data_2016UL_OpenData.py inputFiles_load=EOS_files_split/%s_job${2}.txt \n" % (label) 
    cmd_h5 = "python H5_maker.py -i nano_data2016.root -o %s -j Cert_271036-284044_13TeV_Legacy2016_Collisions16_JSON.txt \n" % oname
else:
    cmd_PFNano = "cmsRun pfnano_mc_2016UL_OpenData.py inputFiles_load=EOS_files_split/%s_job${2}.txt \n" % (label) 
    #cmd_h5 = "python H5_maker.py -i nano_mc2016post.root -o %s --sample_type MC --gen_match \n" % oname
    cmd_h5 = "python H5_maker.py -i nano_mc2016post.root -o %s --sample_type MC \n" % oname


f.write(cmd_PFNano)
f.write(cmd_h5)

cp_cmd = "xrdcp -f %s ${1} \n" % (oname)

f.write(cp_cmd)
f.close()

print_and_do("chmod +x %s" % script_name)
print_and_do("python3 doCondor.py --njobs %i --mem %.0f --overwrite --cmssw --sub  -s %s -n H5_maker_%s"  % (nJobs, mem, script_name, label))
        
