# Read nanoAOD with PF constituents (aka pancakes), apply a pre-selection and output to an H5 file format
import ROOT
from ROOT import TLorentzVector, TFile
import numpy as np
import h5py
from optparse import OptionParser
import sys


from PhysicsTools.NanoAODTools.postprocessing.framework.datamodel import *
from PhysicsTools.NanoAODTools.postprocessing.framework.postprocessor import PostProcessor
from PhysicsTools.NanoAODTools.postprocessing.tools import *
from PhysicsTools.NanoAODTools.postprocessing.modules.jme.JetSysColl import JetSysColl, JetSysObj
from PhysicsTools.NanoAODTools.postprocessing.framework.eventloop import eventLoop
from PhysicsTools.NanoAODTools.postprocessing.framework.preskimming import preSkim

from Utils import *




def nPFCounter(index, event):
    count = 0
    jet_indices = event.FatJetPFCands_jetIdx
    length = len(event.FatJetPFCands_jetIdx)
    for i in range(length):
        if jet_indices[i] == index:
            count += 1
    
    return count

def append_h5(f, name, data):
    prev_size = f[name].shape[0]
    f[name].resize(( prev_size + data.shape[0]), axis=0)
    f[name][prev_size:] = data


def get_branch_mean(inTree, branch_name):

    inTree.Draw(branch_name)
    temp = ROOT.gPad.GetPrimitive("htemp")
    return temp.GetMean()



class Outputer:
    def __init__(self, outputFileName="out.root", batch_size = 5000, sample_type="data", year = 2016, ):

        self.batch_size = batch_size
        self.output_name = outputFileName
        self.sample_type = sample_type
        self.first_write = False
        self.idx = 0
        self.nBatch = 0
        self.n_pf_cands = 150 #how many PF candidates to save (max)
        self.year = year
        self.reset()

    def reset(self):
        self.idx = 0
        self.PFCands = np.zeros((self.batch_size, self.n_pf_cands,11), dtype=np.float32)
        self.jet_kinematics = np.zeros((self.batch_size, 4), dtype=np.float32)
        self.jet_tagging = np.zeros((self.batch_size, 13), dtype=np.float32)
        self.event_info = np.zeros((self.batch_size, 3), dtype=np.int64)

    def sort_pfcands(self, pfcands):
        #Sort by pt
        
        pfcands_pt = np.sqrt(pfcands[:, 0]**2 + pfcands[:, 1]**2)
        sorted_idx = np.flip(np.argsort(pfcands_pt))
        pfcands = pfcands[sorted_idx]
        
        return pfcands

    
    def fill_jet(self, inTree, jet, PFCands, FatJetPFCands):
        
        eventNum = inTree.readBranch('event')
        lumiBlock = inTree.readBranch("luminosityBlock")
        run = inTree.readBranch('run')

        event_info = [run, lumiBlock, eventNum]


        jet_kinematics = [jet.pt, jet.eta, jet.phi, jet.msoftdrop]
        jet_tagging = [jet.nConstituents, jet.tau1, jet.tau2, jet.tau3, jet.tau4, 
            jet.particleNet_H4qvsQCD, jet.particleNet_HbbvsQCD, jet.particleNet_HccvsQCD, jet.particleNet_QCD, jet.particleNet_TvsQCD, 
            jet.particleNet_WvsQCD, jet.particleNet_ZvsQCD, jet.particleNet_mass]

        cands_idxs = [FJCand.pFCandsIdx for FJCand in FatJetPFCands if FJCand.jetIdx == jet.idx] 

        jet_PFCands = []
        for idx in cands_idxs:
            cand = ROOT.Math.PtEtaPhiMVector(PFCands[idx].pt, PFCands[idx].eta, PFCands[idx].phi, PFCands[idx].mass)
            jet_PFCands.append([cand.Px(), cand.Py(), cand.Pz(), cand.E(), 
                PFCands[idx].d0, PFCands[idx].d0Err, PFCands[idx].dz, PFCands[idx].dzErr, PFCands[idx].charge, PFCands[idx].pdgId, PFCands[idx].puppiWeight])


        self.event_info[self.idx] = np.array(event_info, dtype=np.int64)
        self.jet_kinematics[self.idx] = np.array(jet_kinematics, dtype = np.float32)
        self.jet_tagging[self.idx] = np.array(jet_tagging, dtype = np.float32)
        
        if(len(jet_PFCands) > self.n_pf_cands): jet_PFCands = jet_PFCands[:self.n_pf_cands]
        self.PFCands[self.idx,:len(jet_PFCands)] = self.sort_pfcands(np.array(jet_PFCands, dtype = np.float32))

        self.idx +=1
        if(self.idx % self.batch_size == 0): self.write_out()


    def write_out(self):
        self.idx = 0
        print("Writing out batch %i \n" % self.nBatch)
        self.nBatch += 1
        write_size = self.event_info.shape[0]

        if(not self.first_write):
            self.first_write = True
            print("First write, creating dataset with name %s \n" % self.output_name)
            with h5py.File(self.output_name, "w") as f:
                f.create_dataset("event_info", data=self.event_info, chunks = True, maxshape=(None, self.event_info.shape[1]))
                f.create_dataset("jet_kinematics", data=self.jet_kinematics, chunks = True, maxshape=(None, self.jet_kinematics.shape[1]), compression = 'gzip')
                f.create_dataset("jet_tagging", data=self.jet_tagging, chunks = True, maxshape=(None, self.jet_tagging.shape[1]), compression = 'gzip')
                f.create_dataset("PFCands", data=self.PFCands, chunks = True, maxshape=(None, self.PFCands.shape[1], self.PFCands.shape[2]), compression='gzip')

        else:
            with h5py.File(self.output_name, "a") as f:
                append_h5(f,'event_info',self.event_info)
                append_h5(f,'jet_kinematics',self.jet_kinematics)
                append_h5(f,'jet_tagging',self.jet_tagging)
                append_h5(f,'PFCands',self.PFCands)
        self.reset()

    def final_write_out(self ):
        if(self.idx < self.batch_size):
            print("Last batch only filled %i events, shortening arrays \n" % self.idx)
            self.PFCands = self.PFCands[:self.idx]
            self.jet_kinematics = self.jet_kinematics[:self.idx] 
            self.jet_tagging = self.jet_tagging[:self.idx] 
            self.event_info = self.event_info[:self.idx]

        self.write_out()




def NanoReader(inputFileNames=["in.root"], outputFileName="out.root", json = '', year = 2016, nEventsMax = -1, 
        sampleType = "data", gen_match = -1, sort_pfcands=True):
    
    if not ((sampleType == "MC") or (sampleType=="data")):
        print("Error! sampleType needs to be set to either data or MC! Please set correct option and retry.")
        sys.exit()
    
    #Applying standard data quality filters: https://twiki.cern.ch/twiki/bin/view/CMS/MissingETOptionalFiltersRun2#Analysis_Recommendations_for_ana
    filters = ["Flag_goodVertices",
    "Flag_globalSuperTightHalo2016Filter",
    "Flag_HBHENoiseFilter",
    "Flag_HBHENoiseIsoFilter",
    "Flag_EcalDeadCellTriggerPrimitiveFilter",
    "Flag_BadPFMuonFilter",
    "Flag_eeBadScFilter", 
    "Flag_CSCTightHaloFilter",
        ]

    triggers = [
    "HLT_AK8DiPFJet250_200_TrimMass30_BTagCSV_p20",
    "HLT_AK8DiPFJet250_200_TrimMass30",
    "HLT_AK8DiPFJet280_200_TrimMass30_BTagCSV_p087",
    "HLT_AK8DiPFJet280_200_TrimMass30_BTagCSV_p20",
    "HLT_AK8DiPFJet280_200_TrimMass30",
    "HLT_AK8DiPFJet300_200_TrimMass30_BTagCSV_p087",
    "HLT_AK8DiPFJet300_200_TrimMass30_BTagCSV_p20",
    "HLT_AK8DiPFJet300_200_TrimMass30",
    "HLT_AK8PFHT600_TrimR0p1PT0p03Mass50_BTagCSV_p20",
    "HLT_AK8PFHT650_TrimR0p1PT0p03Mass50",
    "HLT_AK8PFHT700_TrimR0p1PT0p03Mass50",
    "HLT_AK8PFHT750_TrimMass50",
    "HLT_AK8PFHT800_TrimMass50",
    "HLT_AK8PFJet140",
    "HLT_AK8PFJet200",
    "HLT_AK8PFJet260",
    "HLT_AK8PFJet320",
    "HLT_AK8PFJet360_TrimMass30",
    "HLT_AK8PFJet400_TrimMass30",
    "HLT_AK8PFJet400",
    "HLT_AK8PFJet40",
    "HLT_AK8PFJet450",
    "HLT_AK8PFJet500",
    "HLT_AK8PFJet60",
    "HLT_AK8PFJet80",
    "HLT_CaloJet500_NoJetID",
    "HLT_DiCentralPFJet170_CFMax0p1",
    "HLT_DiCentralPFJet170",
    "HLT_DiCentralPFJet220_CFMax0p3",
    "HLT_DiCentralPFJet330_CFMax0p5",
    "HLT_DiCentralPFJet430",
    #"HLT_DiJetVBFMu_PassThrough",
    #"HLT_DiJetVBF_PassThrough",
    "HLT_DiPFJetAve100_HFJEC",
    "HLT_DiPFJetAve140",
    "HLT_DiPFJetAve160_HFJEC",
    "HLT_DiPFJetAve200",
    "HLT_DiPFJetAve220_HFJEC",
    "HLT_DiPFJetAve260",
    "HLT_DiPFJetAve300_HFJEC",
    "HLT_DiPFJetAve320",
    "HLT_DiPFJetAve400",
    "HLT_DiPFJetAve40",
    "HLT_DiPFJetAve500",
    "HLT_DiPFJetAve60_HFJEC",
    "HLT_DiPFJetAve60",
    "HLT_DiPFJetAve80_HFJEC",
    "HLT_DiPFJetAve80",
    "HLT_HT2000",
    "HLT_HT2500",
    "HLT_L1_TripleJet_VBF",
    "HLT_PFHT125",
    "HLT_PFHT200",
    "HLT_PFHT250",
    "HLT_PFHT300",
    "HLT_PFHT350",
    "HLT_PFHT400_SixJet30_DoubleBTagCSV_p056",
    "HLT_PFHT400_SixJet30",
    "HLT_PFHT400",
    "HLT_PFHT450_SixJet40_BTagCSV_p056",
    "HLT_PFHT450_SixJet40",
    "HLT_PFHT475",
    "HLT_PFHT550_4JetPt50",
    "HLT_PFHT600",
    "HLT_PFHT650_4JetPt50",
    "HLT_PFHT650_WideJetMJJ900DEtaJJ1p5",
    "HLT_PFHT650_WideJetMJJ950DEtaJJ1p5",
    "HLT_PFHT650",
    "HLT_PFHT750_4JetPt50",
    "HLT_PFHT750_4JetPt70",
    "HLT_PFHT750_4JetPt80",
    "HLT_PFHT800_4JetPt50",
    "HLT_PFHT800",
    "HLT_PFHT850_4JetPt50",
    "HLT_PFHT900",
    "HLT_PFJet140",
    "HLT_PFJet200",
    "HLT_PFJet260",
    "HLT_PFJet320",
    "HLT_PFJet400",
    "HLT_PFJet40",
    "HLT_PFJet450",
    "HLT_PFJet500",
    "HLT_PFJet60",
    "HLT_PFJet80",
    "HLT_QuadPFJet_VBF",
    "HLT_SingleCentralPFJet170_CFMax0p1",
    ]

    nFiles = len(inputFileNames)
    print("Will run over %i files and output to %s " % (nFiles, outputFileName))
    count = 0
    saved = 0

#----------------- Begin loop over files ---------------------------------

    isMC = sampleType == "MC"

    out = Outputer(outputFileName, sample_type=sampleType, year = year, )

    for fileName in inputFileNames:

        print("Opening file %s" % fileName)

        inputFile = TFile.Open(fileName)
        if(not inputFile): #check for null pointer
            print("Unable to open file %s, exting \n" % fileName)
            return 1

        #get input tree
        TTree = inputFile.Get("Events")

        # pre-skimming to good quality events based on json
        if(json != ''):
            elist,jsonFilter = preSkim(TTree, json)

            #number of events to be processed 
            nTotal = elist.GetN() if elist else TTree.GetEntries()
            
            print('Pre-select %d entries out of %s '%(nTotal,TTree.GetEntries()))


            inTree= InputTree(TTree, elist) 
        else:
            nTotal = TTree.GetEntries()
            inTree= InputTree(TTree) 
            print('Running over %i entries \n' % nTotal)


        # Grab event tree from nanoAOD
        eventBranch = inTree.GetBranch('event')
        treeEntries = eventBranch.GetEntries()


# -------- Begin Loop over tree-------------------------------------

        entries = inTree.entries
        for entry in xrange(entries):



            if count % 10000 == 0 :
                print('--------- Processing Event ' + str(count) +'   -- percent complete ' + str(100*count/nTotal/nFiles) + '% -- ')

            count +=1
            # Grab the event
            event = Event(inTree, entry)

            passTrigger = False
            for trig in triggers: passTrigger = passTrigger or inTree.readBranch(trig)
            if(not passTrigger): continue

            
            passFilter = True
            for fil in filters: passFilter = passFilter and inTree.readBranch(fil)
            if(not passFilter): continue
            

            FatJetPFCands = Collection(event, "FatJetPFCands")
            PFCands = Collection(event, "PFCands")
            
            AK8Jets = Collection(event, "FatJet")

            if(isMC and gen_match > 0):
                if(gen_match == top_ID): 
                    gen_part1, gen_part2, W,antiW, q1a,q1b,b1, q2a,q2b,b2  = get_ttbar_gen_parts(event)
                else: 
                    V, q1a, q1b = get_vjets_gen_parts(event, V_ID = gen_match)


            #keep jets with pt > 300, tight id
            jet_min_pt = 300
        
            jet_index = 0
            for i,jet in enumerate(AK8Jets):
                jet.idx = i
                #jetId : bit1 = loose, bit2 = tight, bit3 = tightLepVeto
                #want tight id and tightLepVeto
                if(jet.pt > jet_min_pt and (jet.jetId == 6) and abs(jet.eta) < 2.5):

                    if(gen_match > 0):
                        #require gen match
                        if(gen_match == top_ID):
                            match1 = check_matching(jet, q1a, q1b, b1) == 2
                            match2 = check_matching(jet, q2a, q2b, b2) == 2
                        else:
                            match1 = check_matching(jet, q1a, q1b, None)
                            match2 = False

                        if(match1 or match2):
                            out.fill_jet(inTree, jet, PFCands, FatJetPFCands)
                            saved+=1

                    else:
                        out.fill_jet(inTree, jet, PFCands, FatJetPFCands)
                        saved+=1


            if(nEventsMax > 0 and saved >= nEventsMax): break

    print("Done. Selected %i jets in %i events \n" % (saved, count))
    out.final_write_out()

    print("Outputed to %s" % outputFileName)
    return saved

if(__name__ == "__main__"):

    parser = OptionParser()
    parser.add_option("--sample_type", default = "data", help="MC or data")
    parser.add_option("--gen_match", default =0, type =int, help="Require gen match to specific particle ID")
    parser.add_option("-i", "--input", dest = "fin", default = '', help="Input file name")
    parser.add_option("-o", "--output", dest = "fout", default = 'test.h5', help="Output file name")
    parser.add_option("-j", "--json", default = '', help="Json file name")
    parser.add_option("-y", "--year", type=int, default = 2016, help="Year the sample corresponds to")
    parser.add_option("-n", "--nEvents",  type=int, default = -1, help="Maximum number of events to output (-1 to run over whole file)")

    options, args = parser.parse_args()

    NanoReader(inputFileNames = [options.fin], outputFileName = options.fout, json = options.json, year = options.year, nEventsMax = options.nEvents, 
                sampleType = options.sample_type, gen_match = options.gen_match)


