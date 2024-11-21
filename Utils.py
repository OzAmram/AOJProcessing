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

#pdg ID
top_ID = 6
H_ID = 25
W_ID = 24
Z_ID = 23
B_ID = 5
MAXLEP_ID = 16
MAXLIGHTQUARK_ID = 5


def isFinal(genPart):
    #check if isLastCopy flag is set (Pythia)
    mask = 1 << 13 #13th bit of status flag 
    return (genPart.statusFlags & mask) != 0

def isFirstCopy(statusFlag):
    mask = 1 << 12
    return (statusFlag & mask) != 0

def fromHardProcess(statusFlag):
    mask = 1 << 8
    return (statusFlag & mask) != 0

def ang_dist(phi1, phi2):
    dphi = phi1 - phi2
    if(dphi < -math.pi):
        dphi += 2.* math.pi
    if(dphi > math.pi):
        dphi -= 2.*math.pi
    return dphi

def deltaR(o1, o2):
    return ((o1.eta - o2.eta)**2 + ang_dist(o1.phi, o2.phi)**2)**(0.5)

def check_matching(jet, f1, f2, b_quark):
    #check if quarks are inside ak8 jet
    #0 = no matching, 1 = W_matched, 2 = top_matched

    f1_in = f1 is not None and abs(f1.pdgId) <= B_ID and deltaR(jet,f1) < 0.8
    f2_in = f2 is not None and abs(f2.pdgId) <= B_ID and deltaR(jet,f2) < 0.8
    b_in = b_quark is not None and deltaR(jet,b_quark) < 0.8

    W_match = f1_in and f2_in
    top_match = W_match and b_in

    if(top_match): return 2
    elif(W_match): return 1
    else: return 0

def get_ttbar_gen_parts(event, verbose = True):
    # Find gen level particles from ttbar decays

    GenPartsColl = Collection(event, "GenPart")

    top = anti_top = W = anti_W = fermion1 = anti_fermion1 = b_quark1 = fermion2 = anti_fermion2 = b_quark2 = None

    for genPart in GenPartsColl:
        #tops
        if(abs(genPart.pdgId) == top_ID and isFinal(genPart)):
            if(genPart.pdgId > 0): 
                if(top is None): top = genPart
                else: print("WARNING : Extra top ? ")
            else: 
                if(anti_top is None): anti_top = genPart
                else: print("WARNING : Extra antitop ? ")
        m = genPart.genPartIdxMother
        #W's
        if(abs(genPart.pdgId) == W_ID and isFinal(genPart)):
            if(genPart.pdgId > 0): 
                if(W is None): W = genPart
                else: print("WARNING : Extra W ? ")
            else: 
                if(anti_W is None): anti_W = genPart
                else: print("WARNING : Extra anti W ? ")


    if(top is None or anti_top is None or W is None or anti_W is None):
        print("Couldnt find top or W: ")
        print(top, anti_top, W, anti_W)
        #count = 0
        for genPart in GenPartsColl:
            print(count, genPart.pdgId, genPart.pt, genPart.genPartIdxMother)
            count+=1

    for genPart in GenPartsColl:
        #quarks or leptons from W decay
        m = genPart.genPartIdxMother
        mother = GenPartsColl[m] if m > 0 else None
        w_mother_match = ( mother is W)
        anti_w_mother_match  = (mother is anti_W)
        if(abs(genPart.pdgId) <= MAXLEP_ID and m > 0 and w_mother_match):
            if(genPart.pdgId > 0): 
                if(fermion1 is None): fermion1 = genPart
                elif(verbose): print("WARNING : Extra quark ? ")
            else: 
                if(anti_fermion1 is None): anti_fermion1 = genPart
                elif(verbose): print("WARNING : Extra anti quark ? ")

        elif(abs(genPart.pdgId) <= MAXLEP_ID and m > 0 and anti_w_mother_match):
            if(genPart.pdgId > 0): 
                if(fermion2 is None): fermion2 = genPart
                elif(verbose): print("WARNING : Extra quark ? ")
            else: 
                if(anti_fermion2 is None): anti_fermion2 = genPart
                elif(verbose): print("WARNING : Extra anti quark ? ")

        #find b quark from top
        top_mother_match = (mother is top)
        anti_top_mother_match = (mother is anti_top)
        if(abs(genPart.pdgId) == B_ID and top_mother_match):
            if(b_quark1 is None): b_quark1 = genPart
            elif(verbose): print("WARNING : Extra quark ? ")

        elif(abs(genPart.pdgId) == B_ID and anti_top_mother_match):
            if(b_quark2 is None): b_quark2 = genPart
            elif(verbose): print("WARNING : Extra quark ? ")



    return top, anti_top, W, anti_W, fermion1, anti_fermion1, b_quark1, fermion2, anti_fermion2, b_quark2


def get_vjets_gen_parts(event, V_ID = W_ID, verbose = True):
    # Find gen level paticles from V + jets events (V = W, Z, H)

    GenPartsColl = Collection(event, "GenPart")

    V = fermion1 = anti_fermion1 = None

    for genPart in GenPartsColl:
        #tops
        if(abs(genPart.pdgId) == V_ID and isFinal(genPart)):
            if(V is None): V = genPart
            else: print("WARNING : Extra V ? ")


    if(V is None):
        print("Couldnt find V: ")
        count = 0
        for genPart in GenPartsColl:
            print(count, genPart.pdgId, genPart.pt, genPart.genPartIdxMother)
            count+=1

    for genPart in GenPartsColl:
        #quarks or leptons from W decay
        m = genPart.genPartIdxMother
        mother = GenPartsColl[m] if m > 0 else None
        v_mother_match = ( mother is V)
        if(abs(genPart.pdgId) <= MAXLEP_ID and m > 0 and v_mother_match):
            if(genPart.pdgId > 0): 
                if(fermion1 is None): fermion1 = genPart
                elif(verbose): print("WARNING : Extra quark ? ")
            else: 
                if(anti_fermion1 is None): anti_fermion1 = genPart
                elif(verbose): print("WARNING : Extra anti quark ? ")

    #print(V, fermion1, anti_fermion1)
    #count = 0
    #for genPart in GenPartsColl:
    #    print(count, genPart.pdgId, genPart.pt, genPart.genPartIdxMother)
    #    count+=1

    return V, fermion1, anti_fermion1
