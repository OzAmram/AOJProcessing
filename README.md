# Aspen Open Jets Processing

Code to process the CMS Open Data Sample used to make the Apen Open Jets
sample.

At a high level, we start with CMS data at the `MINIAOD` tier.
We then use the [PFNano](https://opendata.cern.ch/record/12504) package to create a `NANOAOD`-like data format which
additionally contains the Particle Flow candidates (constituents) of the jets.

These PFNano samples are then processed with the `H5_maker.py` which uses
[NANOAOD-tools](https://opendata.cern.ch/record/12507) to read the data, apply 
basic selections and save the resulting jets in an hdf5 format. 

Useful links:

- [CMS Open Data Guide](https://cms-opendata-guide.web.cern.ch/)
- [Getting started with 2015
data](https://opendata.cern.ch/docs/cms-getting-started-2015) (AOJ is based on
2016 but the setup is similar)
- [Description of NanoAOD
format](https://twiki.cern.ch/twiki/bin/view/CMSPublic/WorkBookNanoAOD)
- [Getting Start with NanoAOD Open
Data](https://opendata.cern.ch/docs/cms-getting-started-nanoaod)
- [JetHT 2016G Data](https://opendata.cern.ch/record/30508)
- [JetHT 2016H Data](https://opendata.cern.ch/record/30541)
- [Description of MC Dataset
Names](https://opendata.cern.ch/docs/cms-simulated-dataset-names)

## Setup
First setup the CMS computing environment for 2016 data either using a virtual machine
([link](https://opendata.cern.ch/record/258)) or docker image
([link](https://opendata.cern.ch/docs/cms-guide-docker)).

You will then need to create software release of the version of the CMS
software used for 2016 data processing 

``` cmsrel CMSSW_10_6_30```

You will then need to add the [PFNano](https://opendata.cern.ch/record/12504) package.
This package produces NanoAOD samples from MINIAOD that additionally contains the Particle Flow candidates of each jet.

We also use the
[NanoAODTools](https://github.com/cms-opendata-analyses/nanoAOD-tools) to read
the NanoAOD.

Inside the `src/` directory of your CMSSW release, clone the two needed repos.

```
cd CMSSW_10_6_30/src/
git clone git@github.com:cms-opendata-analyses/PFNanoProducerTool.git PhysicsTools/PFNano
git clone https://github.com/cms-nanoAOD/nanoAOD-tools.git PhysicsTools/NanoAODTools

```

We then build the CMS release with these additional packages

```
cmsenv
scram b
```

## Running 

Production occurs in two steps. First the PFNano tool is run, using a CMS
configuration script, producing an output ROOT in the NANOAOD format.
Then the `H5_maker.py` script is run to apply the basic selections and create
the hdf5 file.

There are separate PFNano CMS configuration scripts for running on Data and MC
samples. 
These configurations customize the PFNano to include only the PFCandidates
associated with AK8 jets (rather than all candidates in the event).

They can be run as
```
cmsRun pfnano_data_2016UL_OpenData.py inputFiles_load=input_files.txt

```

where `input_files.txt` is a text file containing a list of MINIAOD files to be
run over.

Running over a single file (useful for testing) can also be done

```
cmsRun pfnano_data_2016UL_OpenData.py inputFiles=root://eospublic.cern.ch//eos/opendata/cms/Run2016G/JetHT/MINIAOD/UL2016_MiniAODv2-v2/130000/35017A26-8C9D-204D-92B6-3ABFBADF3.root

```

This step will produce a file of the name `nano_data2016.root` or
`nano_mc2016post.root`.

The next step is to run the `H5_maker.py`.

This can be done for a data file as:

```
python H5_maker.py -i nano_data2016.root -o outfile.h5 --sample_type data -j Cert_271036-284044_13TeV_Legacy2016_Collisions16_JSON.txt
```

Where the `Cert` file is the json file containing the list of 2016 data runs validated
by CMS to be of good quality ([link](https://opendata.cern.ch/record/14220)). 

Such a cert file is not necessary when running on MC.

```
python H5_maker.py -i nano_mc2016.root -o outfile.h5 --sample_type MC 
```
When running on MC, optionally the `--gen_match P_ID` flag can be included along with a particle ID.
This will require the saved jets to be matched to a specific type of generator level
particle. 
Specifically it require the quarks from the decay of this particle to be within
deltaR < 0.8 of the selected AK8 jet. 
This can be used to for example save a pure sample of boosted top jets from a ttbar
simulation. 
This requires some customization per MC process to find the correct
generator-level particle to match to.
Currently, top quarks, W, Z and Higgs are supported.

