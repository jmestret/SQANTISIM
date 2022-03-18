#!/usr/bin/env python3
'''
pb_ont_sim.py
Simulation step

@author Jorge Mestre Tomas (jormart2@alumni.uv.es)
@date 20/02/2022
'''

import os
import sys
import subprocess
import pandas
import random
import numpy
import pysam
from collections import defaultdict
    
def pb_simulation(args):
    def counts_to_index(row):
        return id_counts[row['transcript_id']]

    expr_f = os.path.join(os.path.dirname(os.path.abspath(args.trans_index)),'tmp_expression.tsv')
    n = 0
    f_out = open(expr_f, 'w')
    f_out.write('target_id\test_counts\ttpm\n')
    with open(args.trans_index, 'r') as idx:
        header_names = idx.readline()
        header_names = header_names.split()
        i = header_names.index('requested_counts')
        j = header_names.index('requested_tpm')
        for line in idx:
            line = line.split()
            if int(line[i]) == 0:
                continue
            f_out.write(line[0] + '\t' + line[i] + '\t' + line[j] + '\n')
            n += int(line[i])
    idx.close()
    f_out.close()

    if not args.read_count:
        args.read_count = n

    if os.path.isdir(args.dir):
        print('WARNING: output direcory already exists. Overwritting!', file=sys.stderr)
    else:
        os.makedirs(args.dir)
    
    print('***Simulating PacBio reads with IsoSeqSim')
    src_dir = os.path.dirname(os.path.realpath(__file__))
    isoseqsim = os.path.join(src_dir, 'IsoSeqSim/bin/isoseqsim')
    util_dir = os.path.join(src_dir, 'IsoSeqSim/utilities/')
    cmd = [isoseqsim, '-g', str(args.genome),
           '-a', str(args.gtf), '--expr', str(expr_f),
           '--c5', os.path.join(util_dir, '5_end_completeness.PacBio-Sequel.tab'),
           '--c3', os.path.join(util_dir, '3_end_completeness.PacBio-Sequel.tab'),
           '-o', os.path.join(args.dir, 'PacBio_simulated'),
           '-t', os.path.join(args.dir, 'PacBio_simulated.tsv'),
           '--es', '0.01731', '--ed', '0.01090', '--ei', '0.02204',
           '-n', str(args.read_count),
           '-m', 'normal', '--cpu', str(args.cores),
           '--tempdir', os.path.join(args.dir, 'temp_isoseqsim')]
    
    cmd = ' '.join(cmd)
    if subprocess.check_call(cmd, shell=True)!=0:
        print('ERROR running IsoSeqSim: {0}'.format(cmd), file=sys.stderr)
        sys.exit(1)

    os.remove(expr_f)
    print('***Counting PacBio reads')
    output_read_info = open(os.path.join(args.dir, "PacBio_simulated.read_to_isoform.tsv"), "w")
    id_counts = defaultdict(lambda: 0)
    with open(os.path.join(args.dir, 'PacBio_simulated.fasta'), 'r') as sim_fasta:
        for line in sim_fasta:
            if line.startswith('>'):
                line = line.lstrip('>')
                line_split = line.split('_')
                trans_id = '_'.join(line_split[:-4])
                output_read_info.write(line + "\t" + trans_id + "\n")
                id_counts[trans_id] += 1
    sim_fasta.close()
    output_read_info.close()

    trans_index = pandas.read_csv(args.trans_index, sep='\t', header=0)
    trans_index['sim_counts'] = trans_index.apply(counts_to_index, axis=1)
    trans_index.to_csv(args.trans_index, sep='\t', na_rep='NA', header=True, index=False)

    print('***IsoSeqSim simulation done')
    return


def ont_simulation(args):
    def counts_to_index(row):
        return id_counts[row['transcript_id']]
        
    expr_f = os.path.join(os.path.dirname(os.path.abspath(args.trans_index)),'tmp_expression.tsv')
    n = 0
    f_out = open(expr_f, 'w')
    f_out.write('target_id\test_counts\ttpm\n')
    with open(args.trans_index, 'r') as idx:
        header_names = idx.readline()
        header_names = header_names.split()
        i = header_names.index('requested_counts')
        j = header_names.index('requested_tpm')
        for line in idx:
            line = line.split()
            if int(line[i]) == 0:
                continue
            f_out.write(line[0] + '\t' + line[i] + '\t' + line[j] + '\n')
            n += int(line[i])
    idx.close()
    f_out.close()

    if not args.read_count:
        args.read_count = n

    if os.path.isdir(args.dir):
        print('WARNING: output direcory already exists. Overwritting!')
    else:
        os.makedirs(args.dir)

    if args.read_type == 'dRNA':
        model_name = 'human_NA12878_dRNA_Bham1_guppy'
        r_type = 'dRNA'
        uracil = True
    elif args.read_type == 'cDNA':
        model_name = 'human_NA12878_cDNA_Bham1_guppy'
        r_type = 'cDNA_1D2'
        uracil = False
    else:
        print('***ERROR not valid read_type value %s' %(args.read_type), file=sys.stderr)
        return
    
    src_dir = os.path.dirname(os.path.realpath(__file__))
    nanosim = os.path.join(src_dir, 'NanoSim/src/simulator.py')
    models = os.path.join(src_dir, 'NanoSim/pre-trained_models/')
    model_dir = models + model_name + '/'
    if not os.path.exists(model_dir):
        print('***Untar NanoSim model')
        cwd = os.getcwd()
        os.chdir(models)
        res = subprocess.run(['tar', '-xzf', model_name + '.tar.gz'])
        os.chdir(cwd)
        if res.returncode != 0:
            print('Unpacking NanoSim pre-trained model failed', file=sys.stderr)

    print('***Simulating ONT reads with NanoSim')
    cmd = [nanosim, 'transcriptome', '-rt', str(args.rt),
           '-rg', str(args.genome), '-e', str(expr_f),
           '-c', str(model_dir + 'training'),
           '-o', os.path.join(args.dir, 'ONT_simulated'),
           '-n', str(args.read_count), '-r', r_type,
           '-b', 'guppy', '-t', str(args.cores), '--fastq'
    ]

    if uracil:
        cmd.append('--uracil')

    cmd = ' '.join(cmd)
    if subprocess.check_call(cmd, shell=True)!=0:
        print('ERROR running NanoSim: {0}'.format(cmd), file=sys.stderr)
        sys.exit(1)

    os.remove(expr_f)
    print('***Renaming and counting ONT reads')
    ref_trans = set()
    ref_dict = defaultdict(lambda: str())
    with open(args.gtf, 'r') as f_in:
        for line in f_in:
            if not line.startswith('#'):
                line_split = line.split()
                feature = line_split[2]
                if feature == 'exon':
                    trans_id = line_split[line_split.index('transcript_id') + 1]
                    trans_id = trans_id.replace(';', '').replace('"', '')
                    short_id = trans_id.split('.')[0]
                    ref_trans.add(short_id)
                    ref_dict[short_id] = trans_id
    f_in.close()

    fastqs = [os.path.join(args.dir, "ONT_simulated_aligned_reads.fastq"),
              os.path.join(args.dir, "ONT_simulated_unaligned_reads.fastq")]

    n_read = 0
    pair_id = []
    id_counts = defaultdict(lambda: 0)
    f_name = os.path.join(args.dir, 'ONT_simulated.fastq')
    f_out = open(f_name, 'w')

    for f in fastqs:
        f_in = open(f, 'r')
        for line in f_in:
            if line.startswith('@'):
                line = line.lstrip('@')
                trans_id = line.split('_')[0]

                if trans_id not in ref_trans:
                    print('%s was not found in the annotation' %(trans_id), file=sys.stderr)
                else:
                    trans_id = ref_dict[trans_id]
                    
                id_counts[trans_id] += 1
                read_id = trans_id + '_ONT_simulated_read_' + str(n_read)
                n_read += 1
                pair_id.append((read_id, trans_id))

                f_out.write('@{}\n'.format(read_id))
            else:
                f_out.write(line)
    f_in.close()
    f_out.close()

    print('***Saving counts and read-to-isoform files')
    f_name = os.path.join(args.dir, 'ONT_simulated.read_to_isoform.tsv')
    f_out = open(f_name, 'w')

    for pair in pair_id:
        f_out.write(str(pair[0]) + '\t' + str(pair[1]) + '\n')
    f_out.close()

    trans_index = pandas.read_csv(args.trans_index, sep='\t', header=0)
    trans_index['sim_counts'] = trans_index.apply(counts_to_index, axis=1)
    trans_index.to_csv(args.trans_index, sep='\t', na_rep='NA', header=True, index=False)

    print('***NanoSim simulation done')
    return


def illumina_simulation(args):
    def counts_to_index(row):
        return id_counts[row['transcript_id']]

    print('***Simulating Illumina reads')
    print('***Preparing expression matrix')

    count_d = defaultdict(float)
    n = 0
    with open(args.trans_index, 'r') as idx:
        header_names = idx.readline()
        header_names = header_names.split()
        i = header_names.index('requested_counts')
        j = header_names.index('requested_tpm')
        for line in idx:
            line = line.split()
            if int(line[i]) == 0:
                continue
            count_d[line[0]] = float(line[j])
            n += int(line[i])
    idx.close()

    if not args.read_count:
        args.read_count = n

    for k in count_d:
        count_d[k] = round((count_d[k]*args.read_count)/1000000)


    expr_f = os.path.join(args.dir,'tmp_expression.tsv')
    f_out = open(expr_f, 'w')
    with open(args.rt, 'r') as rt:
        for line in rt:
            if line.startswith('>'):
                line = line[1:].strip()
                line = line.split('|') # TODO: this is a quick patch for encode ref
                line = line[0] # TODO: this is a quick patch for encode ref
                f_out.write(str(count_d[line]) + '\n')

    rt.close()
    f_out.close()

    print('***Simulating with Polyester')
    src_dir = os.path.dirname(os.path.realpath(__file__))

    cmd=['Rscript', os.path.join(src_dir,'polyester_sim.R'),
         args.rt, expr_f, args.dir, str(args.seed)]

    cmd = ' '.join(cmd)
    if subprocess.check_call(cmd, shell=True)!=0:
        print('ERROR simulatin with Polyester: {0}'.format(cmd), file=sys.stderr)
        sys.exit(1)
    os.remove(expr_f)
    
    print('***Counting Illumina reads')
    os.rename(os.path.join(args.dir, 'sample_01_1.fasta'), os.path.join(args.dir, 'Illumina_simulated_1.fasta'))
    os.rename(os.path.join(args.dir, 'sample_01_2.fasta'), os.path.join(args.dir, 'Illumina_simulated_2.fasta'))
    
    id_counts = defaultdict(lambda: 0)
    with open(os.path.join(args.dir, 'Illumina_simulated_1.fasta'), 'r') as illumina_sim:
        for line in illumina_sim:
            if line.startswith('>'):
                line = line[1:].strip()
                line = line.split('/')
                line = line[1]
                line = line.split('|') # TODO: this is a quick patch for encode ref
                line = line[0] # TODO: this is a quick patch for encode ref
                id_counts[line] += 1   
    illumina_sim.close()

    trans_index = pandas.read_csv(args.trans_index, sep='\t', header=0)
    trans_index['illumina_counts'] = trans_index.apply(counts_to_index, axis=1)
    trans_index.to_csv(args.trans_index, sep='\t', na_rep='NA', header=True, index=False)

    print('***Polyester simulation done')
    return