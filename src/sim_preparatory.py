#!/usr/bin/env python3
"""
sim_preparatory.py

Modifies index file and add expression values for the simulation step

@author Jorge Mestre Tomas (jormart2@alumni.uv.es)
@date 03/03/2022
"""

import os
import sys
import subprocess
import statistics
import random
import numpy
import pysam
import pandas
from collections import defaultdict


def target_trans(f_idx: str, f_idx_out: str, counts: dict, seed: int) -> tuple:
    """
    Choose those transcripts that will be deleted from the original GTF
    to generate the modified file to use as the reference annotation

    Args:
        f_idx (str): name of the input transcript index file
        f_idx_out (str): name of the output transcript index file
        counts (dict): dictinary with the number of transcripts of each
                       structural category to be deleted
        seed (int): Randomizer seed

    Returns:
        final_target (set): all transcripts to be simulated (deleted from GTF)
    """

    def pick_sim_type(row):
        if row["transcript_id"] in target_trans:
            return "novel"
        else:
            return "known"

    trans_by_SC = defaultdict(lambda: [])
    trans_by_gene = defaultdict(lambda: [])

    target_trans = set()
    target_genes = set()
    ref_trans = set()
    ref_genes = set()

    # Build a list for each SC with all transcripts that were classified there
    with open(f_idx, "r") as cat:
        col_names = cat.readline()
        for line in cat:
            line_split = line.split()
            gene = line_split[1]
            SC = line_split[2]

            trans_by_SC[SC].append(tuple(line_split))
            trans_by_gene[gene].append(tuple(line_split))

    cat.close()

    # Select randomly the transcripts of each SC that are going to be deleted
    # It's important to make sure you don't delete its reference trans or gene
    for SC in counts:
        if counts[SC] > 0:
            SCtrans = trans_by_SC[SC]
            random.Random(seed).shuffle(SCtrans)
            for trans in SCtrans:
                trans_id = trans[0]
                gene_id = trans[1]
                SC = trans[2]
                ref_g = trans[3]
                ref_t = trans[4]

                if (
                    SC in ["full-splice_match", "incomplete-splice_match"]
                    and counts[SC] > 0
                ):
                    if (
                        trans_id not in ref_trans
                        and gene_id not in ref_genes
                        and ref_t not in target_trans
                    ):
                        target_trans.add(trans_id)
                        target_genes.add(gene_id)
                        ref_trans.add(ref_t)
                        counts[SC] -= 1

                elif (
                    SC
                    in [
                        "novel_in_catalog",
                        "novel_not_in_catalog",
                        "genic_intron",
                    ]
                    and counts[SC] > 0
                ):
                    if (
                        trans_id not in ref_trans
                        and gene_id not in ref_genes
                        and gene_id not in target_genes
                        and ref_g not in target_genes
                    ):
                        target_trans.add(trans_id)
                        target_genes.add(gene_id)
                        ref_genes.add(ref_g)
                        counts[SC] -= 1

                elif SC in ["fusion", "antisense", "genic"] and counts[SC] > 0:
                    if (
                        trans_id not in ref_trans
                        and gene_id not in ref_genes
                        and gene_id not in target_genes
                    ):
                        ref_g = trans[3].split("_")
                        for i in ref_g:
                            if i in target_genes:
                                break
                        else:
                            target_trans.add(trans_id)
                            target_genes.add(gene_id)
                            for i in ref_g:
                                ref_genes.add(i)
                            counts[SC] -= 1

                elif SC == "intergenic" and counts[SC] > 0:
                    if (
                        trans_id not in ref_trans
                        and gene_id not in ref_genes
                        and gene_id not in target_genes
                    ):
                        target_trans.add(trans_id)
                        target_genes.add(gene_id)
                        counts[SC] -= 1

                if counts[SC] <= 0:
                    break

    final_target = target_trans
    for gene in trans_by_gene:
        for trans in trans_by_gene[gene]:
            if trans[0] in target_trans:
                trans_by_gene[gene].remove(trans)
                if len(trans_by_gene[gene]) == 0:
                    final_target.add(gene)

    trans_index = pandas.read_csv(f_idx, sep="\t", header=0)
    trans_index["sim_type"] = trans_index.apply(pick_sim_type, axis=1)
    trans_index["sim_type"] = trans_index["sim_type"].fillna("NA")
    trans_index.to_csv(
        f_idx_out, sep="\t", header=True, index=False, na_rep="NA"
    )

    return final_target


def getGeneID(line: str) -> str:
    """
    Returns the gene_id of a GTF line

    Args:
        line (str) line readed from GTF file

    Returns:
        gene_id (str) gene_id from that feature
    """

    line_split = line.split()
    gene_id = line_split[line_split.index("gene_id") + 1]
    gene_id = gene_id.replace(";", "").replace('"', "")

    return gene_id


def getTransID(line: str) -> str:
    """
    Returns the transcript_id of a GTF line

    Args:
        line (str) line readed from GTF file

    Returns:
        trans_id (str) transcript_id from that feature
    """

    try:
        line_split = line.split()
        trans_id = line_split[line_split.index("transcript_id") + 1]
        trans_id = trans_id.replace(";", "").replace('"', "")
    except:
        trans_id = None

    return trans_id


def modifyGTF(f_name_in: str, f_name_out: str, target: list):
    """
    Modify the original GTF deleting target transcripts to simulate specific
    SQANTI3 structural categorires

    Args:
        f_name_in (str) file name of the reference annotation GTF
        f_name_out (str) file name of the modified GTF generated
        target_trans (list) list of transcripts that will be deleted
        ref_genes (list) list of genes that can't be deleted
    """

    f_out = open(f_name_out, "w")

    with open(f_name_in, "r") as gtf_in:
        for line in gtf_in:
            if line.startswith("#"):
                f_out.write(line)
            else:
                gene_id = getGeneID(line)
                trans_id = getTransID(line)
                if gene_id in target or trans_id in target:
                    pass
                else:
                    f_out.write(line)
    gtf_in.close()
    f_out.close()

    return


def simulate_gtf(args):
    print("***Writting modified GTF\n")
    counts = defaultdict(
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

    gtf_modif = os.path.join(args.dir, (args.output + "_modified.gtf"))
    f_idx_out = os.path.join(args.dir, (args.output + "_index.tsv"))

    target = target_trans(args.trans_index, f_idx_out, counts, args.seed)
    modifyGTF(args.gtf, gtf_modif, target)

    return counts


def summary_table_del(counts_ini: dict, counts_end: dict):
    for sc in counts_end:
        counts_ini[sc] -= counts_end[sc]

    print("\033[94m_" * 79 + "\033[0m")
    print("\033[92mS Q A N T I - S I M\033[0m \U0001F4CA")
    print()
    print("GTF modification summary Table \U0001F50E")
    print("\033[94m_" * 79 + "\033[0m")
    for k, v in counts_ini.items():
        print("\033[92m|\033[0m " + k + ": " + str(v))


def create_expr_file_fixed_count(f_idx: str, n_trans: int, read_count: int):
    def fixed_coverage(row):
        if row["transcript_id"] in tot_trans:
            return coverage
        return 0

    novel_trans = []
    known_trans = []

    with open(f_idx, "r") as f_in:
        skip = f_in.readline()
        skip = skip.split()
        i = skip.index('sim_type')
        j = skip.index('transcript_id')
        for line in f_in:
            line = line.split()
            sim_type = line[i]
            if sim_type == "novel":
                novel_trans.append(line[j])
            else:
                known_trans.append(line[j])
    f_in.close()

    random.shuffle(known_trans)
    known_trans = known_trans[: (n_trans - len(novel_trans))]

    tot_trans = len(novel_trans) + len(known_trans)
    if tot_trans != n_trans:
        print(
            "Warning: A higher number than annotated transcripts was requested to simulates, only %s transcript will be simulated"
            % (tot_trans)
        )

    tot_trans = novel_trans + known_trans
    coverage = read_count // n_trans
    tpm = (1000000.0 * coverage) / (
        coverage * n_trans
    )  # Not taking into account transcript length

    trans_index = pandas.read_csv(f_idx, sep="\t", header=0)
    trans_index["requested_counts"] = trans_index.apply(fixed_coverage, axis=1)
    trans_index["requested_tpm"] = round(
        (
            (1000000.0 * trans_index["requested_counts"])
            / (trans_index["requested_counts"] * n_trans)
        ),
        2,
    )
    trans_index["requested_counts"] = trans_index["requested_counts"].fillna(0)
    trans_index["requested_tpm"] = trans_index["requested_tpm"].fillna(0)
    trans_index.to_csv(f_idx, sep="\t", header=True, index=False, na_rep="NA")


def create_expr_file_nbinom(
    f_idx: str, n_trans, nbn_known, nbp_known, nbn_novel, nbp_novel
):
    def nbinom_coverage(row):
        if row["transcript_id"] in novel_trans:
            coverage = nb_novel.pop()
        elif row["transcript_id"] in known_trans:
            coverage = nb_known.pop()
        else:
            coverage = 0
        return coverage

    novel_trans = []
    known_trans = []
    with open(f_idx, "r") as f_in:
        skip = f_in.readline()
        skip = skip.split()
        i = skip.index('sim_type')
        j = skip.index('transcript_id')
        for line in f_in:
            line = line.split()
            sim_type = line[i]
            if sim_type == "novel":
                novel_trans.append(line[j])
            else:
                known_trans.append(line[j])
    f_in.close()

    random.shuffle(known_trans)
    known_trans = known_trans[: (n_trans - len(novel_trans))]

    nb_known = numpy.random.negative_binomial(
        nbn_known, nbp_known, len(known_trans)
    ).tolist()
    nb_known = [
        1 if n == 0 else n for n in nb_known
    ]  # minimum one count per transcript
    nb_novel = numpy.random.negative_binomial(
        nbn_novel, nbp_novel, len(novel_trans)
    ).tolist()
    nb_novel = [
        1 if n == 0 else n for n in nb_novel
    ]  # minimum one count per transcript
    n_reads = sum(nb_known) + sum(nb_novel)

    trans_index = pandas.read_csv(f_idx, sep="\t", header=0)
    trans_index["requested_counts"] = trans_index.apply(
        nbinom_coverage, axis=1
    )
    trans_index["requested_tpm"] = round(
        ((1000000.0 * trans_index["requested_counts"]) / n_reads), 2
    )
    trans_index["requested_counts"] = trans_index["requested_counts"].fillna(0)
    trans_index["requested_tpm"] = trans_index["requested_tpm"].fillna(0)
    trans_index.to_csv(f_idx, sep="\t", header=True, index=False, na_rep="NA")


def create_expr_file_sample(f_idx: str, ref_trans, reads, tech):
    def sample_coverage(row):
        if row["transcript_id"] in novel_trans:
            coverage = novel_expr.pop()
        elif row["transcript_id"] in known_trans:
            coverage = known_expr.pop()
        else:
            coverage = 0
        return coverage

    sam_file = "_".join(f_idx.split("_")[:-1]) + "_align_" + tech + ".sam"

    if tech == "pb":
        cmd = [
            "minimap2",
            ref_trans,
            reads,
            "-x",
            "map-pb",
            "-a",
            "--secondary=no",
            "-o",
            sam_file,
        ]
    elif tech == "ont":
        cmd = [
            "minimap2",
            ref_trans,
            reads,
            "-x",
            "map-ont",
            "-a",
            "--secondary=no",
            "-o",
            sam_file,
        ]

    cmd = " ".join(cmd)
    sys.stdout.flush()
    if subprocess.check_call(cmd, shell=True) != 0:
        print("ERROR running minimap2: {0}".format(cmd), file=sys.stderr)
        sys.exit(1)

    trans_counts = defaultdict(lambda: 0)

    with pysam.AlignmentFile(sam_file, "r") as sam_file_in:
        for align in sam_file_in:
            trans_id = align.reference_name

            if (
                align.reference_id == -1
                or align.is_supplementary
                or align.is_secondary
            ):
                continue
            trans_counts[trans_id] += 1
    os.remove(sam_file)

    expr_distr = list(trans_counts.values())
    expr_distr.sort()
    median_poss = round(len(expr_distr) / 2)
    median_half1 = statistics.median(expr_distr[0:median_poss])
    median_half2 = statistics.median(expr_distr[median_poss : len(expr_distr)])
    prob = numpy.linspace(
        start=0.1, stop=0.9, num=int(median_half2 - median_half1)
    )
    prob = (
        ([0.1] * int(median_half1 - min(expr_distr)))
        + list(prob)
        + ([0.9] * int(max(expr_distr) - median_half2))
    )

    n_trans = len(expr_distr)
    novel_trans = []
    known_trans = []
    with open(f_idx, "r") as f_in:
        skip = f_in.readline()
        skip = skip.split()
        i = skip.index('sim_type')
        j = skip.index('transcript_id')
        for line in f_in:
            line = line.split()
            sim_type = line[i]
            if sim_type == "novel":
                novel_trans.append(line[j])
            else:
                known_trans.append(line[j])
    f_in.close()

    random.shuffle(known_trans)
    known_trans = known_trans[: (n_trans - len(novel_trans))]
    if (len(novel_trans) + len(known_trans)) < n_trans:
        n_trans = len(novel_trans) + len(known_trans)
        expr_distr = expr_distr[
            -n_trans,
        ]

    min_expr = min(expr_distr) + 1
    novel_expr = []
    n_novel = 0
    while n_novel < len(novel_trans):
        s = random.choice(expr_distr)
        r = random.uniform(0, 1)
        if r > prob[(s - min_expr)]:
            novel_expr.append(s)
            n_novel += 1

    known_expr = []
    n_known = 0
    while n_known < len(known_trans):
        s = random.choice(expr_distr)
        r = random.uniform(0, 1)
        if r < prob[(s - min_expr)]:
            known_expr.append(s)
            n_known += 1

    n_reads = sum(novel_expr) + sum(known_expr)

    trans_index = pandas.read_csv(f_idx, sep="\t", header=0)
    trans_index["requested_counts"] = trans_index.apply(
        sample_coverage, axis=1
    )
    trans_index["requested_tpm"] = round(
        ((1000000.0 * trans_index["requested_counts"]) / n_reads), 2
    )
    trans_index["requested_counts"] = trans_index["requested_counts"].fillna(0)
    trans_index["requested_tpm"] = trans_index["requested_tpm"].fillna(0)
    trans_index.to_csv(f_idx, sep="\t", header=True, index=False, na_rep="NA")
