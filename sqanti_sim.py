#!/usr/bin/env python3
'''
sqanti3_sim.py

Wrapper for long-read RNA-seq simulators (NanoSim and IsoSeqSim) to simulate
controlled novelty and degradation of transcripts based on SQANTI3 structural
categories

@author Jorge Mestre Tomas (jormart2@alumni.uv.es)
@date 19/01/2022
'''

__version__ = '0.1'

import argparse
import os
import sys
import random
import numpy
from collections import defaultdict
from src import classif_gtf
from src import pb_ont_sim
from src import sqanti3_stats
from src import sim_preparatory


def classif(input):
    '''Classify transcripts in SQANTI3 structural categories

    Given a GTF annotation generates an index file with the SQANTI3 structural
    category to simulate of each transcript

    Args:
        input (list): arguments to parse
    '''

    parser = argparse.ArgumentParser(prog='sqanti_sim.py classif', description='sqanti_sim.py classif parse options')
    parser.add_argument('--gtf', type = str,  help = '\t\tReference annotation in GTF format', required=True)
    parser.add_argument('-o', '--output', default='sqanti_sim', help = '\t\tPrefix for output files')
    parser.add_argument('-d', '--dir', default='.', help = '\t\tDirectory for output files (default: .)')
    parser.add_argument('--min_ref_len', default=0, type=int, help='\t\tMinimum reference transcript length (default: 0 bp as in largasp challenge 1 evaluation)')
    parser.add_argument('-k', '--cores', default=1, type=int, help = '\t\tNumber of cores to run in parallel')

    args, unknown = parser.parse_known_args(input)

    if unknown:
        print('classif mode unrecognized arguments: {}\n'.format(' '.join(unknown)), file=sys.stderr)

    # Classify GTF transcripts in SQANTI3 structural categories
    trans_info = classif_gtf.classify_gtf(args)

    # Print summary table
    print('***Summary table from categorization\n')
    classif_gtf.summary_table_cat(trans_info)

    print('***Finished succesfully')
    return


def preparatory(input):
    '''Generates the expression matrix to simulate

    Given the nove and known transcripts to simulate and its counts, generates
    the expression matrix to give as input to the long-read RNA-seq simulators

    Args:
        input (list): arguments to parse
    '''

    parser = argparse.ArgumentParser(prog='sqanti_sim.py preparatory', description='sqanti_sim.py preparatory parse options')
    parser.add_argument('mode', default = 'equal', choices=['equal', 'custom', 'sample'],  help = '\t\tDifferent modes to generate the expression matrix: equal (simulate with equal coverage for all reads), custom (simulate with diferent negative binomial distributions for novel and known transcripts) or sample (simulate using a real sample)')
    parser.add_argument('-i', '--trans_index', type= str,  help = '\t\tFile with transcript information generated with SQANTI-SIM', required=True)
    parser.add_argument('--gtf', type=str, help = '\t\tReference annotation in GTF format', required=True)
    parser.add_argument('-o', '--output', default=str(), help = '\t\tPrefix for output files')
    parser.add_argument('-d', '--dir', default='.', help = '\t\tDirectory for output files (default: .)')
    parser.add_argument('--read_count', default = 50000, type=int,  help = '\t\tNumber of reads to simulate (required for "equal" mode)')
    parser.add_argument('-nt', '--trans_number', default = 10000, type=int,  help = '\t\tNumber of different transcripts to simulate (required for "equal" or "custom" mode)')
    parser.add_argument('--nbn_known',default=50,type = float, help='\t\tAverage read count per known transcript to simulate (i.e., the parameter "n" of the Negative Binomial distribution) (required for "custom" mode)')
    parser.add_argument('--nbp_known',default=0.5,type = float, help='\t\tThe parameter "p" of the Negative Binomial distribution for known transcripts (required for "custom" mode)')
    parser.add_argument('--nbn_novel',default=5,type = float, help='\t\tAverage read count per novel transcript to simulate (i.e., the parameter "n" of the Negative Binomial distribution) (required for "custom" mode)')
    parser.add_argument('--nbp_novel',default=0.5,type = float, help='\t\tThe parameter "p" of the Negative Binomial distribution for novel transcripts (required for "custom" mode)')
    parser.add_argument('--rt', default=str(), type=str, help='\t\tReference transcripts in FASTA format (required for "sample" mode)')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--pb_reads', default=str(), type = str,  help = '\t\tInput PacBio reads for quantification (required for "sample" mode)')
    group.add_argument('--ont_reads', default=str(), type = str,  help = '\t\tInput ONT reads for quantification (required for "sample" mode)')
    parser.add_argument('--ISM', default=0, type=int, help = '\t\tNumber of incomplete-splice-matches to delete')
    parser.add_argument('--NIC', default=0, type=int, help = '\t\tNumber of novel-in-catalog to delete')
    parser.add_argument('--NNC', default=0, type=int, help = '\t\tNumber of novel-not-in-catalog to delete')
    parser.add_argument('--Fusion', default=0, type=int, help = '\t\tNumber of Fusion to delete')
    parser.add_argument('--Antisense', default=0, type=int, help = '\t\tNumber of Antisense to delete')
    parser.add_argument('--GG', default=0, type=int, help = '\t\tNumber of Genic-genomic to delete')
    parser.add_argument('--GI', default=0, type=int, help = '\t\tNumber of Genic-intron to delete')
    parser.add_argument('--Intergenic', default=0, type=int, help = '\t\tNumber of Intergenic to delete') 
    parser.add_argument('-k', '--cores', default=1, type=int, help = '\t\tNumber of cores to run in parallel')   
    parser.add_argument('-s', '--seed', help='\t\tRandomizer seed [123]', default=123, type=int)

    args, unknown = parser.parse_known_args(input)

    if unknown:
        print('preparatory mode unrecognized arguments: {}\n'.format(' '.join(unknown)), file=sys.stderr)

    if args.mode == 'equal':
        if not args.read_count or not args.trans_number:
            print('sqanti_sim.py preparatory equal: error: the following arguments are required: --read_count, --trans_number', file=sys.stderr)
            sys.exit(1)
    elif args.mode == 'custom':
        if not args.nbn_known or not args.nbp_known or not args.nbn_novel or not args.nbp_novel:
            print('sqanti_sim.py preparatory custom: error: the following arguments are required: --trans_number, --nbn_known, --nbp_known, --nbn_novel, --nbp_novel', file=sys.stderr)
            sys.exit(1)
    elif args.mode == 'sample':
        if not args.rt or not (args.pb_reads or args.ont_reads):
            print('sqanti_sim.py preparatory sample: error: the following arguments are required: --rt, {--pb_reads, --ont_reads}', file=sys.stderr)
            sys.exit(1)
        
    if not args.output:
        output = os.path.basename(args.trans_index).split('_')
        args.output = '_'.join(output[:-1])
    
    # Modify GTF
    random.seed(args.seed)
    numpy.random.seed(args.seed)

    counts_end = sim_preparatory.simulate_gtf(args)

    print('***Summary table from GTF modification\n')
    counts_ini = defaultdict(lambda: 0, {
        'full-splice_match': 0,
        'incomplete-splice_match': args.ISM,
        'novel_in_catalog': args.NIC,
        'novel_not_in_catalog':args.NNC,
        'fusion' : args.Fusion,
        'antisense': args.Antisense,
        'genic_intron': args.GI,
        'genic' :args.GG,
        'intergenic':args.Intergenic
    }) 
    sim_preparatory.summary_table_del(counts_ini, counts_end)

    expression_out = os.path.join(args.dir, (args.output + '_expression.tsv'))
    index_out = os.path.join(args.dir, (args.output + '_index.tsv'))

    # Generate expression matrix
    if args.mode == 'equal':
        sim_preparatory.create_expr_file_fixed_count(args.trans_index, args.trans_number,
                                            args.read_count, expression_out, index_out)
    elif args.mode == 'custom':
        sim_preparatory.create_expr_file_nbinom(args.trans_index, args.trans_number,
                                            args.nbn_known, args.nbp_known, 
                                            args.nbn_novel, args.nbp_novel,
                                            expression_out, index_out)
    elif args.mode == 'sample':
        if args.pb_reads:
            sim_preparatory.create_expr_file_sample(args.trans_index, 
                                            args.rt, args.pb_reads,
                                            expression_out, index_out, 'pb')
        else:
            sim_preparatory.create_expr_file_sample(args.trans_index, 
                                            args.rt, args.ont_reads,
                                            expression_out, index_out, 'ont')
    else:
        print('Not valid sim mode', file=sys.stderr)


def sim(input):
    '''Simulate reads

    Simulate PacBio and/or ONT reads using the IsoSeqSim or NanoSim pipelines

    Args:
        input (list): arguments to parse
    '''

    parser = argparse.ArgumentParser(prog='sqanti_sim.py sim', description='sqanti_sim.py sim parse options')
    parser.add_argument('--gtf', type = str,  help = '\t\tReference annotation in GTF format', required=True)
    parser.add_argument('--genome', default = False,  help = '\t\tReference genome FASTA', required=True)
    parser.add_argument('--rt', default=str(), type=str, help='\t\tReference transcripts in FASTA format')
    parser.add_argument('-i', '--trans_index', type= str,  help = '\t\tFile with transcript information generated with SQANTI-SIM', required=True)
    parser.add_argument('--read_type', default = 'dRNA', type=str,  help = '\t\tRead type for NanoSim simulation')
    parser.add_argument('-o', '--output', default='sqanti_sim', help = '\t\tPrefix for output files')
    parser.add_argument('-d', '--dir', default='.', help = '\t\tDirectory for output files (default: .)')
    parser.add_argument('-k', '--cores', default=1, type=int, help = '\t\tNumber of cores to run in parallel')  
    parser.add_argument('--pb', action='store_true', help = '\t\tIf used the program will simulate PacBio reads with IsoSeqSim')
    parser.add_argument('--ont', action='store_true', help = '\t\tIf used the program will simulate ONT reads with NanoSim')
    parser.add_argument('--read_count', default = None, type=int,  help = '\t\tNumber of reads to simulate (if not given it will use the counts of the given expression file)')
    parser.add_argument('-s', '--seed', help='\t\tRandomizer seed [123]', default=123, type=int)

    args, unknown = parser.parse_known_args(input)

    if unknown:
        print('sim mode unrecognized arguments: {}\n'.format(' '.join(unknown)), file=sys.stderr)

    if not args.ont and not args.pb:
        print('sqanti_sim.py sim: error: one of the following arguments is required: --pb, --ont', file=sys.stderr)
        sys.exit(1)

    if args.ont and not args.rt:
        print('sqanti_sim.py sim: error: the following arguments are required when using --ont: --rt', file=sys.stderr)
        sys.exit(1)

    random.seed(args.seed)
    numpy.random.seed(args.seed)
    args.output = os.path.join(args.dir, args.output)

    if args.pb:
        pb_ont_sim.pb_simulation(args)
    if args.ont:
        pb_ont_sim.ont_simulation(args)


def eval(input):
    '''Generates SQANTI-SIM report

    Runs SQANTI3 with the reconstructed transcript retrieved by your pipeline
    and generates the SQANTI-SIM report with the evaluation metrics

    Args:
        input (list): arguments to parse
    '''

    parser = argparse.ArgumentParser(prog='sqanti_sim.py eval', description='sqanti_sim.py eval parse options')
    parser.add_argument('--isoforms', default = str(),  help = '\t\tGTF with trancriptome reconstructed with your pipeline', required=True)
    parser.add_argument('--gtf', type = str,  help = '\t\tReference annotation in GTF format', required=True)
    parser.add_argument('--genome', default = False,  help = '\t\tReference genome FASTA', required=True)
    parser.add_argument('-i', '--trans_index', type= str,  help = '\t\tFile with transcript information generated with SQANTI-SIM', required=True)
    parser.add_argument('-o', '--output', default='sqanti_sim', help = '\t\tPrefix for output files')
    parser.add_argument('-d', '--dir', default='.', help = '\t\tDirectory for output files (default: .)')
    parser.add_argument('--min_ref_len', default=0, type=int, help='\t\tMinimum reference transcript length (use the same as in the classif step)')
    parser.add_argument('-k', '--cores', default=1, type=int, help = '\t\tNumber of cores to run in parallel')
    
    args, unknown = parser.parse_known_args(input)

    if unknown:
        print('sim mode unrecognized arguments: {}\n'.format(' '.join(unknown)), file=sys.stderr)

    sqanti3_stats.sqanti3_stats(args)
    

#####################################
#                                   #
#               MAIN                #
#                                   #
#####################################

print(
    '''                                                                      
      _____  ____            _   _ _______ _____      _____ _____ __  __  
     / ____|/ __ \     /\   | \ | |__   __|_   _|    / ____|_   _|  \/  | 
    | (___ | |  | |   /  \  |  \| |  | |    | |_____| (___   | | | \  / | 
     \___ \| |  | |  / /\ \ | . ` |  | |    | |______\___ \  | | | |\/| | 
     ____) | |__| | / ____ \| |\  |  | |   _| |_     ____) |_| |_| |  | | 
    |_____/ \___\_\/_/    \_\_| \_|  |_|  |_____|   |_____/|_____|_|  |_| 
                                                                          
              A SIMULATOR OF CONTROLLED NOVELTY AND DEGRADATION           
                    OF TRANSCRIPTS SEQUENCED BY LONG-READS                
    '''
    )

if len(sys.argv) < 2:
    print('usage: python sqanti_sim.py <mode> --help\n', file=sys.stderr)
    print('modes: classif, preparatory, sim, eval\n', file=sys.stderr)
    sys.exit(1)

else:
    mode = sys.argv[1].lower()
    input = sys.argv[2:]

if mode == 'classif':
    print('CLASSIF MODE')
    res = classif(input)

elif mode == 'preparatory':
    print('PREPARATORY MODE')
    res = preparatory(input)

elif mode == 'sim':
    print('SIM MODE')
    res = sim(input)

elif mode == 'eval':
    print('EVAL MODE')
    res = eval(input)

elif mode in ['--version', '-v']:
	sys.stderr.write('SQANTI-SIM v0.0.0\n')

else:
   print('usage: python sqanti_sim.py <mode> --help\n', file=sys.stderr)
   print('modes: classif, preparatory, sim, eval\n', file=sys.stderr)
   sys.exit(1) 