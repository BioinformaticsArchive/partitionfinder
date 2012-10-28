#Copyright (C) 2011 Robert Lanfear and Brett Calcott
#
#This program is free software: you can redistribute it and/or modify it
#under the terms of the GNU General Public License as published by the
#Free Software Foundation, either version 3 of the License, or (at your
#option) any later version.
#
#This program is distributed in the hope that it will be useful, but
#WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#General Public License for more details. You should have received a copy
#of the GNU General Public License along with this program.  If not, see
#<http://www.gnu.org/licenses/>. PartitionFinder also includes the PhyML
#program and the PyParsing library both of which are protected by their
#own licenses and conditions, using PartitionFinder implies that you
#agree with those licences and conditions as well.

"""Run phyml and parse the output"""

import logging
log = logging.getLogger("analysis")

import subprocess, shlex, os, shutil, sys

from pyparsing import (
    Word, Literal, nums, Suppress, ParseException,
    SkipTo,
    )

from phyml_models import get_model_commandline

_binary_name = 'phyml'
if sys.platform == 'win32':
    _binary_name += ".exe"

from util import PartitionFinderError
class PhymlError(PartitionFinderError):
    pass

# def init_phyml(cfg):
    # global _phyml_binary
    # pth = find_program()
    # if sys.platform == 'win32':
        # pth = relocate_binary(cfg, pth)
    # _phyml_binary = pth

# def relocate_binary(cfg, pth):
    # """Relocate binary in windows cos it spits the dummy on long paths"""
    # newpth = os.path.join(cfg.base_path, _binary_name)
    # shutil.copy(pth, newpth)
    # return newpth

# def shutdown_phyml(cfg):
    # newpth = os.path.join(cfg.base_path, _binary_name)
    # if os.path.exists(newpth):
        # os.remove(newpth)

def find_program():
    """Locate the binary ..."""
    pth = os.path.abspath(__file__)

    # Split off the name and the directory...
    pth, notused = os.path.split(pth)
    pth, notused = os.path.split(pth)
    pth = os.path.join(pth, "programs", _binary_name)
    pth = os.path.normpath(pth)

    log.debug("Checking for program %s", _binary_name)
    if not os.path.exists(pth) or not os.path.isfile(pth):
        log.error("No such file: '%s'", pth)
        raise PhymlError
    log.debug("Found program %s at '%s'", _binary_name, pth)
    return pth

# def alt_run_phyml(command):
    # log.debug("Running command '%s'", command)

    # # Note: We use shlex.split as it does a proper job of handling command
    # # lines that are complex
    # try:
        # subprocess.check_call(shlex.split(command), shell=False)
    # 
    # except subprocess.CalledProcessError:
        # log.error("command '%s' failed to execute successfully", command)
        # raise PhymlError

_phyml_binary = None
def run_phyml(command):
    global _phyml_binary
    if _phyml_binary is None:
        _phyml_binary = find_program()

    #turn off any memory checking in PhyML - thanks Jess Thomas for pointing out this problem
    command = "%s --no_memory_check" %(command)

    # Add in the command file
    log.debug("Running 'phyml %s'", command)
    command = "\"%s\" %s" % (_phyml_binary, command)

    # Note: We use shlex.split as it does a proper job of handling command
    # lines that are complex
    p = subprocess.Popen(
        shlex.split(command),
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    # Capture the output, we might put it into the errors
    stdout, stderr = p.communicate()
    # p.terminate()

    if p.returncode != 0:
        log.error("Phyml did not execute successfully")
        log.error("Phyml output follows, in case it's helpful for finding the problem")
        log.error("%s", stdout)
        log.error("%s", stderr)
        raise PhymlError

def dupfile(src, dst):
    # Make a copy or a symlink so that we don't overwrite different model runs
    # of the same alignment
    
    # TODO maybe this should throw...?
    try:
        if os.path.exists(dst):
            os.remove(dst)
        shutil.copyfile(src, dst)
    except OSError:
        log.error("Cannot link/copy file %s to %s", src, dst)
        raise PhymlError

def make_topology(alignment_path, datatype):
	'''Make a BioNJ tree to start the analysis'''
	log.info("Making BioNJ tree for %s", alignment_path)

	# First get the BioNJ topology like this:
	if datatype=="DNA":
		command = "-i '%s' -o n -b 0" % (alignment_path)
	elif datatype=="protein":
		command = "-i '%s' -o n -b 0 -d aa" % (alignment_path)
	else:
		log.error("Unrecognised datatype: '%s'" % (datatype))
		raise(PhymlError)
		
	run_phyml(command)
	output_path = make_tree_path(alignment_path)
	return output_path

def make_branch_lengths(alignment_path, topology_path):
    # Now we re-estimate branchlengths using a GTR+I+G model on the (unpartitioned) dataset
    log.info("Estimating GTR+I+G branch lengths on tree")
    dir_path, fname = os.path.split(topology_path)
    tree_path = os.path.join(dir_path, 'topology_tree.phy')
    log.debug("Copying %s to %s", topology_path, tree_path)
    dupfile(topology_path, tree_path)

    command = "-i '%s' -u '%s' -m GTR -c 4 -a e -v e -o lr -b 0" % (
        alignment_path, tree_path)
    run_phyml(command)

    output_path = make_tree_path(alignment_path)
    log.info("Branchlength estimation finished")

    # Now return the path of the final tree alignment
    return output_path

def make_branch_lengths_protein(alignment_path, topology_path):
    # Now we re-estimate branchlengths using the LG model on the (unpartitioned) dataset
    log.info("Estimating LG+F branch lengths on tree")
    dir_path, fname = os.path.split(topology_path)
    tree_path = os.path.join(dir_path, 'topology_tree.phy')
    log.debug("Copying %s to %s", topology_path, tree_path)
    dupfile(topology_path, tree_path)

    command = "-i '%s' -u '%s' -m LG -c 1 -v 0 -f m -d aa -o lr -b 0" % (
        alignment_path, tree_path)
    run_phyml(command)

    output_path = make_tree_path(alignment_path)
    log.info("Branchlength estimation finished")

    # Now return the path of the final tree alignment
    return output_path


def analyse(model, alignment_path, tree_path, branchlengths):
    """Do the analysis -- this will overwrite stuff!"""

    # Move it to a new name to stop phyml stomping on different model analyses
    # dupfile(alignment_path, analysis_path)
    model_params = get_model_commandline(model)

    if branchlengths == 'linked':
        #constrain all branchlengths to be equal
        bl = ' --constrained_lens '
    elif branchlengths == 'unlinked':
        #let branchlenghts vary among subsets
        bl = ''
    else:
        # WTF?
        log.error("Unknown option for branchlengths: %s", branchlengths)
        raise PhymlError

    command = "--run_id %s -b 0 -i '%s' -u '%s' %s %s" % (
        model, alignment_path, tree_path, model_params, bl)
    run_phyml(command)

    # Now get rid of this -- we have the original elsewhere
    # os.remove(analysis_path)

def make_tree_path(alignment_path):
    pth, ext = os.path.splitext(alignment_path)
    return pth + ".phy_phyml_tree.txt"

def make_output_path(aln_path, model):
    # analyse_path = os.path.join(root_path, name + ".phy")
    pth, ext = os.path.splitext(aln_path)
    stats_path = "%s.phy_phyml_stats_%s.txt" % (pth, model)
    tree_path = "%s.phy_phyml_tree_%s.txt" % (pth, model)
    return stats_path, tree_path

class PhymlResult(object):
    def __init__(self, lnl, seconds):
        self.lnl = lnl
        self.seconds = seconds

    def __str__(self):
        return "PhymlResult(lnl:%s, secs:%s)" % (self.lnl, self.seconds) 

class Parser(object):
    def __init__(self):
        FLOAT = Word(nums + '.-').setParseAction(lambda x: float(x[0]))
        INTEGER = Word(nums + '-').setParseAction(lambda x: int(x[0]))

        OB = Suppress("(")
        CB = Suppress(")")
        LNL_LABEL = Literal("Log-likelihood:")
        TIME_LABEL = Literal("Time used:")
        HMS = Word(nums + "hms") # A bit rough...

        lnl = (LNL_LABEL + FLOAT("lnl"))
        time = (TIME_LABEL + HMS("time") + OB + INTEGER("seconds") + Suppress("seconds") + CB)

        # Shorthand...
        def nextbit(label, val):
            return Suppress(SkipTo(label)) + val

        # Just look for these things
        self.root_parser = \
                nextbit(LNL_LABEL, lnl) +\
                nextbit(TIME_LABEL, time)

    def parse(self, text):
        # log.info("Parsing phyml output...")
        try:
            tokens = self.root_parser.parseString(text)
        except ParseException, p:
            log.error(str(p))
            raise PhymlError

        return PhymlResult(lnl=tokens.lnl, seconds=tokens.seconds)

# Stateless, so safe for use across threads. HMMMM, REALLY?
the_parser = Parser()

def parse(text):
    return the_parser.parse(text)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    import tempfile, os
    from alignment import TestAlignment
    import phyml_models 
    alignment = TestAlignment("""
4 2208
spp1     CTTGAGGTTCAGAATGGTAATGAA------GTGCTGGTGCTGGAAGTTCAGCAGCAGCTCGGCGGCGGTATCGTACGTACCATCGCCATGGGTTCTTCCGACGGTCTGCGTCGCGGTCTGGATGTAAAAGACCTCGAGCACCCGATCGAAGTCCCAGTTGGTAAAGCAACACTGGGTCGTATCATGAACGTACTGGGTCAGCCAGTAGACATGAAGGGCGACATCGGTGAAGAAGAGCGTTGGGCT---------------ATCCACCGTGAAGCACCATCCTATGAAGAGCTGTCAAGCTCTCAGGAACTGCTGGAAACCGGCATCAAAGTTATCGACCTGATGTGTCCGTTTGCGAAGGGCGGTAAAGTTGGTCTGTTCGGTGGTGCGGGTGTAGGTAAAACCGTAAACATGATGGAGCTTATTCGTAACATCGCGATCGAGCACTCCGGTTATTCTGTGTTTGCGGGCGTAGGTGAACGTACTCGTGAGGGTAACGACTTCTACCACGAAATGACCGACTCCAACGTTATCGAT---------------------AAAGTTTCTCTGGTTTATGGCCAGATGAACGAGCCACCAGGTAACCGTCTGCGCGTTGCGCTGACCGGTCTGACCATGGCTGAGAAGTTCCGTGACGAAGGTCGCGACGTACTGCTGTTCGTCGATAACATCTATCGTTACACCCTGGCAGGTACTGAAGTTTCAGCACTGCTGGGTCGTATGCCTTCAGCGGTAGGTTACCAGCCGACTCTGGCGGAAGAAATGGGCGTTCGCATTCCAACGCTGGAAGAGTGTGATATCTGCCACGGCAGCGGCGCTAAAGCCGGTTCGAAGCCGCAGACCTGTCCTACCTGTCACGGTGCAGGCCAGGTACAGATGCGCCAGGGCTTCTTCGCTGTACAGCAGACCTGTCCACACTGCCAGGGCCGCGGTACGCTGATCAAAGATCCGTGCAACAAATGTCACGGTCATGGTCGCGTAGAGAAAACCAAAACCCTGTCCGTAAAAATTCCGGCAGGCGTTGATACCGGCGATCGTATTCGTCTGACTGGCGAAGGTGAAGCTGGTGAGCACGGCGCACCGGCAGGCGATCTGTACGTTCAGGTGCAGGTGAAGCAGCACGCTATTTTCGAGCGTGAAGGCAACAACCTGTACTGTGAAGTGCCGATCAACTTCTCAATGGCGGCTCTTGGCGGCGAGATTGAAGTGCCGACGCTTGATGGTCGCGTGAAGCTGAAAGTTCCGGGCGAAACGCAAACTGGCAAGCTGTTCCGTATGCGTGGCAAGGGCGTGAAGTCCGTGCGCGGCGGTGCACAGGGCGACCTTCTGTGCCGCGTGGTGGTCGAGACACCGGTAGGTCTTAACGAGAAGCAGAAACAGCTGCTCAAAGATCTGCAGGAAAGTTTTGGCGGCCCAACGGGTGAAAACAACGTTGTTAACGCCCTGTCGCAGAAACTGGAATTGCTGATCCGCCGCGAAGGCAAAGTACATCAGCAAACTTATGTCCATGGTGTGCCACAGGCTCCGCTGGCGGTAACCGGTGAAACGGAAGTGACCGGTACACAGGTGCGTTTCTGGCCAAGCCACGAAACCTTCACCAACGTAATCGAATTCGAATATGAGATTCTGGCAAAACGTCTGCGCGAGCTGTCATTCCTGAACTCCGGCGTTTCCATCCGTCTGCGCGATAAGCGTGAC---GGCAAAGAAGACCATTTCCACTATGAAGGTGGTATCAAGGCGTTTATTGAGTATCTCAATAAAAATAAAACGCCTATCCACCCGAATATCTTCTACTTCTCCACCGAA---AAAGACGGTATTGGCGTAGAAGTGGCGTTGCAGTGGAACGATGGTTTCCAGGAAAACATCTACTGCTTCACCAACAACATTCCACAGCGTGATGGCGGTACTCACCTTGCAGGCTTCCGTGCGGCGATGACCCGTACGCTGAACGCTTACATGGACAAAGAAGGCTACAGCAAAAAAGCCAAA------GTCAGCGCCACCGGTGATGATGCCCGTGAAGGCCTGATTGCCGTCGTTTCCGTGAAAGTACCGGATCCGAAATTCTCCTCTCAGACTAAAGACAAACTGGTCTCTTCTGAGGTGAAAACGGCGGTAGAACAGCAGATGAATGAACTGCTGAGCGAATACCTGCTGGAAAACCCGTCTGACGCCAAAATC
spp2     CTTGAGGTACAAAATGGTAATGAG------AGCCTGGTGCTGGAAGTTCAGCAGCAGCTCGGTGGTGGTATCGTACGTGCTATCGCCATGGGTTCTTCCGACGGTCTGCGTCGTGGTCTGGAAGTTAAAGACCTTGAGCACCCGATCGAAGTCCCGGTTGGTAAAGCAACGCTGGGTCGTATCATGAACGTGCTGGGTCAGCCGATCGATATGAAAGGCGACATCGGCGAAGAAGAACGTTGGGCG---------------ATTCACCGTGCAGCACCTTCCTATGAAGAGCTCTCCAGCTCTCAGGAACTGCTGGAAACCGGCATCAAAGTTATCGACCTGATGTGTCCGTTCGCGAAGGGCGGTAAAGTCGGTCTGTTCGGTGGTGCGGGTGTTGGTAAAACCGTAAACATGATGGAGCTGATCCGTAACATCGCGATCGAACACTCCGGTTACTCCGTGTTTGCTGGTGTTGGTGAGCGTACTCGTGAGGGTAACGACTTCTACCACGAAATGACCGACTCCAACGTTCTGGAT---------------------AAAGTATCCCTGGTTTACGGCCAGATGAACGAGCCGCCGGGAAACCGTCTGCGCGTTGCACTGACCGGCCTGACCATGGCTGAGAAATTCCGTGACGAAGGTCGTGACGTTCTGCTGTTCGTCGATAACATCTATCGTTATACCCTGGCCGGTACAGAAGTATCTGCACTGCTGGGTCGTATGCCTTCTGCGGTAGGTTATCAGCCGACGCTGGCGGAAGAGATGGGCGTTCGTATCCCGACGCTGGAAGAGTGCGACGTCTGCCACGGCAGCGGCGCGAAATCTGGCAGCAAACCGCAGACCTGTCCGACCTGTCATGGTCAGGGCCAGGTGCAGATGCGTCAGGGCTTCTTCGCCGTTCAGCAGACCTGTCCGCATTGTCAGGGGCGCGGTACGCTGATTAAAGATCCGTGCAACAAATGTCACGGTCACGGTCGCGTTGAGAAAACCAAAACCCTGTCGGTCAAAATCCCGGCGGGCGTGGATACCGGCGATCGTATTCGTCTGTCAGGAGAAGGCGAAGCGGGCGAACACGGTGCACCAGCAGGCGATCTGTACGTTCAGGTCCAGGTTAAGCAGCACGCCATCTTTGAGCGTGAAGGCAATAACCTGTACTGCGAAGTGCCTATTAACTTCACCATGGCAGCCCTCGGCGGCGAGATTGAAGTCCCGACGCTGGATGGCCGGGTGAATCTCAAAGTGCCTGGCGAAACGCAAACCGGCAAACTGTTCCGCATGCGCGGTAAAGGTGTGAAATCCGTGCGCGGTGGTGCTCAGGGCGACCTGCTGTGCCGCGTGGTGGTTGAAACACCAGTCGGGCTGAACGATAAGCAGAAACAGCTGCTGAAGGACCTGCAGGAAAGTTTTGGCGGACCAACGGGCGAGAAAAACGTGGTTAACGCCCTGTCGCAGAAGCTGGAGCTGGTTATTCAGCGCGACAATAAAGTTCACCGTCAGATCTATGCGCACGGTGTGCCGCAGGCTCCGCTGGCAGTGACCGGTGAGACCGAAAAAACCGGCACCATGGTACGTTTCTGGCCAAGCTATGAAACCTTCACCAACGTTGTCGAGTTCGAATACGAGATCCTGGCAAAACGTCTGCGTGAGCTGTCGTTCCTGAACTCCGGGGTTTCTATCCGTCTGCGTGACAAGCGTGAC---GGTAAAGAAGACCATTTCCACTACGAAGGCGGCATCAAGGCGTTCGTTGAGTATCTCAATAAGAACAAAACGCCGATCCACCCGAATATCTTCTACTTCTCCACCGAA---AAAGACGGTATTGGCGTCGAAGTAGCGCTGCAGTGGAACGACGGCTTCCAGGAAAACATCTACTGCTTCACCAACAACATCCCGCAGCGCGATGGCGGTACTCACCTTGCGGGCTTCCGCGCGGCGATGACCCGTACCCTGAACGCCTATATGGACAAAGAAGGCTACAGCAAAAAAGCCAAA------GTCAGCGCTACCGGCGACGATGCGCGTGAAGGCCTGATTGCCGTTGTCTCCGTGAAGGTTCCGGATCCGAAATTCTCCTCGCAGACCAAAGACAAACTGGTCTCCTCCGAGGTGAAAACCGCGGTTGAACAGCAGATGAATGAACTGCTGAACGAATACCTGCTGGAAAATCCGTCTGACGCGAAAATC
spp3     CTTGAGGTACAGAATAACAGCGAG------AAGCTGGTGCTGGAAGTTCAGCAGCAGCTCGGCGGCGGTATCGTACGTACCATCGCAATGGGTTCTTCCGACGGTCTGCGTCGTGGTCTGGAAGTGAAAGACCTCGAGCACCCGATCGAAGTCCCGGTAGGTAAAGCGACCCTGGGTCGTATCATGAACGTGCTGGGTCAGCCAATCGATATGAAAGGCGACATCGGCGAAGAAGATCGTTGGGCG---------------ATTCACCGCGCAGCACCTTCCTATGAAGAGCTGTCCAGCTCTCAGGAACTGCTGGAAACCGGCATCAAAGTTATCGACCTGATTTGTCCGTTCGCTAAGGGCGGTAAAGTTGGTCTGTTCGGTGGTGCGGGCGTAGGTAAAACCGTAAACATGATGGAGCTGATCCGTAACATCGCGATCGAGCACTCCGGTTACTCCGTGTTTGCAGGCGTGGGTGAGCGTACTCGTGAGGGTAACGACTTCTACCACGAGATGACCGACTCCAACGTTCTGGAC---------------------AAAGTTGCACTGGTTTACGGCCAGATGAACGAGCCGCCAGGTAACCGTCTGCGCGTAGCGCTGACCGGTCTGACCATCGCGGAGAAATTCCGTGACGAAGGCCGTGACGTTCTGCTGTTCGTCGATAACATCTATCGTTATACCCTGGCCGGTACAGAAGTTTCTGCACTGCTGGGTCGTATGCCATCTGCGGTAGGTTATCAGCCTACTCTGGCAGAAGAGATGGGTGTTCGTATCCCGACGCTGGAAGAGTGTGAAGTTTGCCACGGCAGCGGCGCGAAAAAAGGTTCTTCTCCGCAGACCTGTCCAACCTGTCATGGACAGGGCCAGGTGCAGATGCGTCAGGGCTTCTTCACCGTGCAGCAAAGCTGCCCGCACTGCCAGGGCCGCGGTACCATCATTAAAGATCCGTGCACCAACTGTCACGGCCATGGCCGCGTAGAGAAAACCAAAACGCTGTCGGTAAAAATTCCGGCAGGCGTGGATACCGGCGATCGTATCCGCCTTTCTGGTGAAGGCGAAGCGGGCGAGCACGGCGCACCTTCAGGCGATCTGTACGTTCAGGTTCAGGTGAAACAGCACCCAATCTTCGAGCGTGAAGGCAATAACCTGTACTGCGAAGTGCCGATCAACTTTGCGATGGCTGCGCTGGGCGGGGAAATTGAAGTGCCGACCCTTGACGGCCGCGTTAAGCTGAAGGTACCGAGCGAAACGCAAACCGGCAAGCTGTTCCGCATGCGCGGTAAAGGCGTGAAATCCGTACGCGGTGGCGCGCAGGGCGATCTGCTGTGCCGCGTCGTCGTTGAAACTCCGGTTAGCCTGAACGAAAAGCAGAAGAAACTGCTGCGTGATTTGGAAGAGAGCTTTGGCGGCCCAACGGGGGCGAACAATGTTGTGAACGCCCTGTCCCAGAAGCTGGAGCTGCTGATTCGCCGCGAAGGCAAAACCCATCAGCAAACCTACGTGCACGGTGTGCCGCAGGCTCCGCTGGCGGTCACCGGTGAAACCGAACTGACCGGTACCCAGGTGCGTTTCTGGCCGAGCCATGAAACCTTCACCAACGTCACCGAATTCGAATATGACATCCTGGCTAAGCGCCTGCGTGAGCTGTCGTTCCTGAACTCCGGCGTCTCTATTCGCCTGAACGATAAGCGCGAC---GGCAAGCAGGATCACTTCCACTACGAAGGCGGCATCAAGGCGTTTGTTGAGTACCTCAACAAGAACAAAACCCCGATTCACCCGAACGTCTTCTATTTCAGCACTGAA---AAAGACGGCATCGGCGTGGAAGTGGCGCTGCAGTGGAACGACGGCTTCCAGGAAAATATCTACTGCTTTACCAACAACATTCCTCAGCGCGACGGCGGTACTCACCTTGCGGGCTTCCGCGCGGCGATGACCCGTACCCTGAACGCCTATATGGACAAAGAAGGCTACAGCAAAAAAGCCAAA------GTGAGCGCCACCGGTGACGATGCGCGTGAAGGCCTGATTGCCGTAGTGTCCGTGAAGGTGCCGGATCCGAAGTTCTCTTCCCAGACCAAAGACAAACTGGTTTCTTCGGAAGTGAAATCCGCGGTTGAACAGCAGATGAACGAACTGCTGGCTGAATACCTGCTGGAAAATCCGGGCGACGCAAAAATT
spp4     CTCGAGGTGAAAAATGGTGATGCT------CGTCTGGTGCTGGAAGTTCAGCAGCAGCTGGGTGGTGGCGTGGTTCGTACCATCGCCATGGGTACTTCTGACGGCCTGAAGCGCGGTCTGGAAGTTACCGACCTGAAAAAACCTATCCAGGTTCCGGTTGGTAAAGCAACCCTCGGCCGTATCATGAACGTATTGGGTGAGCCAATCGACATGAAAGGCGACCTGCAGAATGACGACGGCACTGTAGTAGAGGTTTCCTCTATTCACCGTGCAGCACCTTCGTATGAAGATCAGTCTAACTCGCAGGAACTGCTGGAAACCGGCATCAAGGTTATCGACCTGATGTGTCCGTTCGCTAAGGGCGGTAAAGTCGGTCTGTTCGGTGGTGCGGGTGTAGGTAAAACCGTAAACATGATGGAGCTGATCCGTAACATCGCGGCTGAGCACTCAGGTTATTCGGTATTTGCTGGTGTGGGTGAGCGTACTCGTGAGGGTAACGACTTCTACCACGAAATGACTGACTCCAACGTTATCGAT---------------------AAAGTAGCGCTGGTGTATGGCCAGATGAACGAGCCGCCGGGTAACCGTCTGCGCGTAGCACTGACCGGTTTGACCATGGCGGAAAAATTCCGTGATGAAGGCCGTGACGTTCTGCTGTTCATCGACAACATCTATCGTTACACCCTGGCCGGTACTGAAGTATCAGCACTGCTGGGTCGTATGCCATCTGCGGTAGGCTATCAGCCAACGCTGGCAGAAGAGATGGGTGTGCGCATTCCAACACTGGAAGAGTGCGATGTCTGCCACGGTAGCGGCGCGAAAGCGGGGACCAAACCGCAGACCTGTCATACCTGTCATGGCGCAGGCCAGGTGCAGATGCGTCAGGGCTTCTTCACTGTGCAGCAGGCGTGTCCGACCTGTCACGGTCGCGGTTCAGTGATCAAAGATCCGTGCAATGCTTGTCATGGTCACGGTCGCGTTGAGCGCAGTAAAACCCTGTCGGTGAAAATTCCAGCAGGCGTGGATACCGGCGATCGCATTCGTCTGACCGGCGAAGGTGAAGCGGGCGAACAGGGCGCACCAGCGGGCGATCTGTACGTTCAGGTTTCGGTGAAAAAGCACCCGATCTTTGAGCGTGAAGATAACAACCTATATTGCGAAGTGCCGATTAACTTTGCGATGGCAGCATTGGGTGGCGAGATTGAAGTGCCGACGCTTGATGGGCGTGTGAACCTGAAAGTGCCTTCTGAAACGCAAACTGGCAAGCTGTTCCGCATGCGCGGTAAAGGCGTGAAATCGGTGCGTGGTGGTGCGGTAGGCGATTTGCTGTGTCGTGTGGTGGTGGAAACGCCAGTTAGCCTCAATGACAAACAGAAAGCGTTACTGCGTGAACTGGAAGAGAGTTTTGGCGGCCCGAGCGGTGAGAAAAACGTCGTAAACGCCCTGTCACAGAAGCTGGAGCTGACCATTCGCCGTGAAGGCAAAGTGCATCAGCAGGTTTATCAGCACGGCGTGCCGCAGGCACCGCTGGCGGTGTCCGGTGATACCGATGCAACCGGTACTCGCGTGCGTTTCTGGCCGAGCTACGAAACCTTCACCAATGTGATTGAGTTTGAGTACGAAATCCTGGCGAAACGCCTGCGTGAACTGTCGTTCCTGAACTCTGGCGTTTCGATTCGTCTGGAAGACAAACGCGAC---GGCAAGAACGATCACTTCCACTACGAAGGCGGCATCAAGGCGTTCGTTGAGTATCTCAACAAGAACAAAACCCCGATTCACCCAACGGTGTTCTACTTCTCGACGGAG---AAAGATGGCATTGGCGTGGAAGTGGCGCTGCAGTGGAACGATGGTTTCCAGGAAAACATCTACTGCTTCACCAACAACATTCCACAGCGCGACGGCGGTACGCACCTGGCGGGCTTCCGTGCGGCAATGACGCGTACGCTGAATGCCTACATGGATAAAGAAGGCTACAGCAAAAAAGCCAAA------GTCAGTGCGACCGGTGACGATGCGCGTGAAGGCCTGATTGCAGTGGTTTCCGTGAAAGTGCCGGATCCGAAATTCTCTTCTCAGACCAAAGATAAGCTGGTCTCTTCTGAAGTGAAATCGGCGGTTGAGCAGCAGATGAACGAACTGCTGGCGGAATACCTGCTGGAAAATCCGTCTGACGCGAAAATC
""")
    tmp = tempfile.mkdtemp()
    pth = os.path.join(tmp, 'test.phy')
    alignment.write(pth)
    tree_path = make_tree(pth)
    log.info("Tree is %s:", open(tree_path).read())

    for model in phyml_models.get_all_models():
        log.info("Analysing using model %s:" % model)
        out_pth = analyse(model, pth, tree_path)
        output = open(out_pth, 'rb').read()
        res = parse(output)
        log.info("Result is %s", res)

    # shutil.rmtree(tmp)
