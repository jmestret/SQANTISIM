#!/usr/bin/env python3
"""
sqanti3_sim.py

Wrapper for long-read RNA-seq simulators (NanoSim and IsoSeqSim) to simulate
controlled novelty and degradation of transcripts based on SQANTI3 structural
categories

@author Jorge Martinez Tomas (jormart2@alumni.uv.es)
@date 19/01/2022
"""

__version__ = "1.0b1"

import argparse
import numpy
import os
import random
import sys
from collections import defaultdict
from src import classif_gtf
from src import pb_ont_sim
from src import sim_preparatory
from src import sqanti3_stats


def classif(input: list):
    """Classify transcripts in SQANTI3 structural categories

    Given a GTF annotation generates an index file with the SQANTI3 structural
    category to simulate of each transcript

    Args:
        input (list): arguments to parse
    """

    parser = argparse.ArgumentParser( prog="sqanti_sim.py classif", description="sqanti_sim.py classif parse options", )
    parser.add_argument( "--gtf", type=str, help="\t\tReference annotation in GTF format", required=True, )
    parser.add_argument( "-o", "--output", default="sqanti_sim", help="\t\tPrefix for output file", )
    parser.add_argument( "-d", "--dir", default=".", help="\t\tDirectory for output files (default: .)", )
    parser.add_argument( "-k", "--cores", default=1, type=int, help="\t\tNumber of cores to run in parallel", )

    args, unknown = parser.parse_known_args(input)

    if unknown:
        print(
            "[SQANTI-SIM] classif mode unrecognized arguments: {}\n".format(
                " ".join(unknown)
            ),
            file=sys.stderr,
        )

    # Classify GTF transcripts in SQANTI3 structural categories
    trans_info = classif_gtf.classify_gtf(args)
    
    print("[SQANTI-SIM] Summary table from categorization\n")
    classif_gtf.summary_table_cat(trans_info)

    print("[SQANTI-SIM] classif step finished succesfully")


def preparatory(input: list):
    """Modifies reference annotation GTF and builds expression matrix

    Given the novel and known transcripts to simulate and its counts, generates
    the expression matrix to give as input to the long-read RNA-seq simulators
    and generetes the modified GTF to use as reference annotation in your tool

    Args:
        input (list): arguments to parse
    """

    parser = argparse.ArgumentParser( prog="sqanti_sim.py preparatory", description="sqanti_sim.py preparatory parse options", )
    parser.add_argument( "mode", default="equal", choices=["equal", "custom", "sample"], help="\t\tDifferent modes to generate the expression matrix: equal (simulate with equal coverage for all reads), custom (simulate with diferent negative binomial distributions for novel and known transcripts) or sample (simulate using a real sample)", )
    parser.add_argument( "-i", "--trans_index", type=str, help="\t\tFile with transcript information generated with SQANTI-SIM", required=True, )
    parser.add_argument( "--gtf", type=str, help="\t\tReference annotation in GTF format", required=True, )
    parser.add_argument( "-o", "--output", default=str(), help="\t\tPrefix for output files" )
    parser.add_argument( "-d", "--dir", default=".", help="\t\tDirectory for output files (default: .)", )
    parser.add_argument( "--read_count", default=50000, type=int, help="\t\tNumber of reads to simulate (required for 'equal' mode)", )
    parser.add_argument( "-nt", "--trans_number", default=10000, type=int, help="\t\tNumber of different transcripts to simulate (required for 'equal' or 'custom' mode)", )
    parser.add_argument( "--nbn_known", default=15, type=float, help="\t\tAverage read count per known transcript to simulate (i.e., the parameter 'n' of the Negative Binomial distribution) (required for 'custom' mode)", )
    parser.add_argument( "--nbp_known", default=0.5, type=float, help="\t\tThe parameter 'p' of the Negative Binomial distribution for known transcripts (required for 'custom' mode)", )
    parser.add_argument( "--nbn_novel", default=5, type=float, help="\t\tAverage read count per novel transcript to simulate (i.e., the parameter 'n' of the Negative Binomial distribution) (required for 'custom' mode)", )
    parser.add_argument( "--nbp_novel", default=0.5, type=float, help="\t\tThe parameter 'p' of the Negative Binomial distribution for novel transcripts (required for 'custom' mode)", )
    parser.add_argument( "--rt", default=str(), type=str, help="\t\tReference transcripts in FASTA format (required for 'sample' mode)", )
    group = parser.add_mutually_exclusive_group()
    group.add_argument( "--pb_reads", default=str(), type=str, help="\t\tInput PacBio reads for quantification (required for 'sample' mode)", )
    group.add_argument( "--ont_reads", default=str(), type=str, help="\t\tInput ONT reads for quantification (required for 'sample' mode)", )
    parser.add_argument( "--diff_exp", action="store_true", help="\t\tIf used the program will simulate different expression values for novel and known transcripts", )
    parser.add_argument( "--low_prob", default=0.25, type=float, help="\t\tLow value of prob vector (required for 'sample' mode diff_exp)", )
    parser.add_argument( "--high_prob", default=0.75, type=float, help="\t\tHigh value of prob vector (required for 'sample' mode diff_exp)", )
    parser.add_argument( "--ISM", default=0, type=int, help="\t\tNumber of incomplete-splice-matches to delete", )
    parser.add_argument( "--NIC", default=0, type=int, help="\t\tNumber of novel-in-catalog to delete", )
    parser.add_argument( "--NNC", default=0, type=int, help="\t\tNumber of novel-not-in-catalog to delete", )
    parser.add_argument( "--Fusion", default=0, type=int, help="\t\tNumber of Fusion to delete" )
    parser.add_argument( "--Antisense", default=0, type=int, help="\t\tNumber of Antisense to delete", )
    parser.add_argument( "--GG", default=0, type=int, help="\t\tNumber of Genic-genomic to delete", )
    parser.add_argument( "--GI", default=0, type=int, help="\t\tNumber of Genic-intron to delete", )
    parser.add_argument( "--Intergenic", default=0, type=int, help="\t\tNumber of Intergenic to delete", )
    parser.add_argument( "-k", "--cores", default=1, type=int, help="\t\tNumber of cores to run in parallel", )
    parser.add_argument( "-s", "--seed", help="\t\tRandomizer seed [123]", default=123, type=int )

    args, unknown = parser.parse_known_args(input)

    if unknown:
        print(
            "[SQANTI-SIM] preparatory mode unrecognized arguments: {}\n".format(
                " ".join(unknown)
            ),
            file=sys.stderr,
        )

    if not os.path.isdir(args.dir):
        os.makedirs(args.dir)

    print("[SQANTI-SIM] Parameters for expression file:")
    if args.mode == "equal":
        print("[SQANTI-SIM] -Mode: equal")
        print("[SQANTI-SIM] -Nº transcripts: %s" %(args.trans_number))
        print("[SQANTI-SIM] -Nº reads: %s" %(args.read_count))

    elif args.mode == "custom":
        print("[SQANTI-SIM] -Mode: custom")
        print("[SQANTI-SIM] -Nº transcripts: %s" %(args.trans_number))
        print("[SQANTI-SIM] -Known NB mean count: %s" %(args.nbn_known))
        print("[SQANTI-SIM] -Known NB probability: %s" %(args.nbp_known))
        print("[SQANTI-SIM] -novel NB mean count: %s" %(args.nbn_novel))
        print("[SQANTI-SIM] -novel NB probability: %s" %(args.nbp_novel))

    elif args.mode == "sample":
        print("[SQANTI-SIM] -Mode: sample")
        print("[SQANTI-SIM] -Reference transcriptome: %s" %(args.rt))
        if args.pb_reads:
            print("[SQANTI-SIM] -PacBio reads: %s" %(args.pb_reads))
        else:
            print("[SQANTI-SIM] -ONT reads: %s" %(args.ont_reads))

    if not args.output:
        output = os.path.basename(args.trans_index).split("_")
        args.output = "_".join(output[:-1])

    # Modify GTF
    random.seed(args.seed)
    numpy.random.seed(args.seed)
    counts_end = sim_preparatory.simulate_gtf(args)

    print("[SQANTI-SIM] Deleted transcripts from GTF\n")
    counts_ini = defaultdict(
        lambda: 0,
        {
            "full-splice_match": 0,
            "incomplete-splice_match": args.ISM,
            "novel_in_catalog": args.NIC,
            "novel_not_in_catalog": args.NNC,
            "fusion": args.Fusion,
            "antisense": args.Antisense,
            "genic_intron": args.GI,
            "genic": args.GG,
            "intergenic": args.Intergenic,
        },
    )
    sim_preparatory.summary_table_del(counts_ini, counts_end)

    # Generate expression matrix
    print("[SQANTI-SIM] Generating expression matrix\n")
    index_file = os.path.join(args.dir, (args.output + "_index.tsv"))

    if args.mode == "equal":
        sim_preparatory.create_expr_file_fixed_count(index_file, args)

    elif args.mode == "custom":
        sim_preparatory.create_expr_file_nbinom(index_file, args)

    elif args.mode == "sample":
        if args.pb_reads:
            sim_preparatory.create_expr_file_sample(index_file, args, "pb")
        else:
            sim_preparatory.create_expr_file_sample(index_file, args, "ont")

    print("[SQANTI-SIM] preparatory step finished succesfully")
    

def sim(input: list):
    """Simulate reads

    Simulate PacBio and/or ONT reads using the IsoSeqSim or NanoSim pipelines.
    It can also simulate Illumina reads using the polyester pipeline

    Args:
        input (list): arguments to parse
    """

    parser = argparse.ArgumentParser( prog="sqanti_sim.py sim", description="sqanti_sim.py sim parse options" )
    parser.add_argument( "--gtf", type=str, help="\t\tReference annotation in GTF format", required=True, )
    parser.add_argument( "--genome", default=False, help="\t\tReference genome FASTA", required=True, )
    parser.add_argument( "--rt", default=str(), type=str, help="\t\tReference transcripts in FASTA format (required for simulating ONT or Illumina reads)", )
    parser.add_argument( "-i", "--trans_index", type=str, help="\t\tFile with transcript information generated with SQANTI-SIM", required=True, )
    parser.add_argument( "--read_type", default="dRNA", type=str, help="\t\tRead type for NanoSim simulation", )
    parser.add_argument( "-d", "--dir", default=".", help="\t\tDirectory for output files (default: .)", )
    parser.add_argument( "-k", "--cores", default=1, type=int, help="\t\tNumber of cores to run in parallel", )
    group = parser.add_mutually_exclusive_group()
    group.add_argument( "--pb", action="store_true", help="\t\tIf used the program will simulate PacBio reads with IsoSeqSim", )
    group.add_argument( "--ont", action="store_true", help="\t\tIf used the program will simulate ONT reads with NanoSim", )
    parser.add_argument( "--illumina", action="store_true", help="\t\tIf used the program will simulate Illumina reads with RSEM", )
    parser.add_argument( "--long_count", default=None, type=int, help="\t\tNumber of long reads to simulate (if not given it will use the counts of the given expression file)", )
    parser.add_argument( "--short_count", default=None, type=int, help="\t\tNumber of short reads to simulate (if not given it will use the counts of the given expression file)", )
    parser.add_argument( "--min_support", default=3, type=int, help="\t\tMinimum number of supporting reads for an isoform", )
    parser.add_argument( "-s", "--seed", help="\t\tRandomizer seed [123]", default=123, type=int )

    args, unknown = parser.parse_known_args(input)

    if unknown:
        print(
            "[SQANTI-SIM] sim mode unrecognized arguments: {}\n".format(" ".join(unknown)),
            file=sys.stderr,
        )

    if (args.ont or args.illumina) and not args.rt:
        print(
            "[SQANTI-SIM] sqanti_sim.py sim ERROR: the following arguments are required when using --ont or --illumina: --rt",
            file=sys.stderr,
        )
        sys.exit(1)

    # Simulation with IsoSeqSim, NanoSim and/or Polyester
    random.seed(args.seed)
    numpy.random.seed(args.seed)

    if args.pb:
        pb_ont_sim.pb_simulation(args)
    if args.ont:
        pb_ont_sim.ont_simulation(args)
    if args.illumina:
        pb_ont_sim.illumina_simulation(args)

    print("[SQANTI-SIM] sim step finished succesfully")


def eval(input: list):
    """Generates SQANTI-SIM report

    Run SQANTI3 with the reconstructed transcripts retrieved by your pipeline
    and generates the SQANTI-SIM report with the evaluation metrics

    Args:
        input (list): arguments to parse
    """

    parser = argparse.ArgumentParser( prog="sqanti_sim.py eval", description="sqanti_sim.py eval parse options", )
    parser.add_argument( "--isoforms", default=str(), help="\t\tGTF with trancriptome reconstructed with your pipeline", required=True, )
    parser.add_argument( "--gtf", type=str, help="\t\tReference annotation in GTF format", required=True, )
    parser.add_argument( "--genome", default=False, help="\t\tReference genome FASTA", required=True, )
    parser.add_argument( "-i", "--trans_index", type=str, help="\t\tFile with transcript information generated with SQANTI-SIM", required=True, )
    parser.add_argument( "-o", "--output", default="sqanti_sim", help="\t\tPrefix for output files", )
    parser.add_argument( "-d", "--dir", default=".", help="\t\tDirectory for output files (default: .)", )
    parser.add_argument( "--short_reads", help="\t\tFile Of File Names (fofn, space separated) with paths to FASTA or FASTQ from Short-Read RNA-Seq. If expression or coverage files are not provided, Kallisto (just for pair-end data) and STAR, respectively, will be run to calculate them.", required=False, )
    parser.add_argument( "--cage_peak", help="\t\tFANTOM5 Cage Peak (BED format, optional)" )
    parser.add_argument('--STAR_index' , help='\t\t Directory of indexed genome by STAR', required=False)
    parser.add_argument( "-k", "--cores", default=1, type=int, help="\t\tNumber of cores to run in parallel", )

    args, unknown = parser.parse_known_args(input)

    if unknown:
        print(
            "[SQANTI-SIM] sim mode unrecognized arguments: {}\n".format(" ".join(unknown)),
            file=sys.stderr,
        )

    sqanti3_stats.sqanti3_stats(args)

    print("[SQANTI-SIM] eval step finished succesfully")


#####################################
#                                   #
#               MAIN                #
#                                   #
#####################################

print(
    """                                                                      
      _____  ____            _   _ _______ _____      _____ _____ __  __  
     / ____|/ __ \     /\   | \ | |__   __|_   _|    / ____|_   _|  \/  | 
    | (___ | |  | |   /  \  |  \| |  | |    | |_____| (___   | | | \  / | 
     \___ \| |  | |  / /\ \ | . ` |  | |    | |______\___ \  | | | |\/| | 
     ____) | |__| | / ____ \| |\  |  | |   _| |_     ____) |_| |_| |  | | 
    |_____/ \___\_\/_/    \_\_| \_|  |_|  |_____|   |_____/|_____|_|  |_| 
                                                                          
              A SIMULATOR OF CONTROLLED NOVELTY AND DEGRADATION           
                    OF TRANSCRIPTS SEQUENCED BY LONG-READS                
    """
)

if len(sys.argv) < 2:
    print("[SQANTI-SIM] usage: python sqanti_sim.py <mode> --help\n", file=sys.stderr)
    print("[SQANTI-SIM] modes: classif, preparatory, sim, eval\n", file=sys.stderr)
    sys.exit(1)

else:
    mode = sys.argv[1].lower()
    input = sys.argv[2:]

if mode == "classif":
    print("[SQANTI-SIM] CLASSIF MODE")
    res = classif(input)

elif mode == "preparatory":
    print("[SQANTI-SIM] PREPARATORY MODE")
    res = preparatory(input)

elif mode == "sim":
    print("[SQANTI-SIM] SIM MODE")
    res = sim(input)

elif mode == "eval":
    print("[SQANTI-SIM] EVAL MODE")
    res = eval(input)

elif mode in ["--version", "-v"]:
    print("[SQANTI-SIM] SQANTI-SIM %s\n" %(__version__))

else:
    print("[SQANTI-SIM] usage: python sqanti_sim.py <mode> --help\n", file=sys.stderr)
    print("[SQANTI-SIM] modes: classif, preparatory, sim, eval\n", file=sys.stderr)
    sys.exit(1)
