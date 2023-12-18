#!/usr/bin/env python

"""
Rhyming dictionary: driver program.

This program takes an English word (or several English words) and displays all
known rhyming words.
"""

import argparse
import codecs
import collections
import logging
import os
import re

import rhyme

CMU_PATHS = (
  f"{os.environ.get('DATA_DIR', 'data')}/cmudict-0.7b.utf8",
  f"{os.environ.get('DATA_DIR', 'data')}/cmudict-0.7b",
  f"{os.environ.get('DATA_DIR', 'data')}/cmudict.0.7b",
  f"{os.environ.get('DATA_DIR', 'data')}/cmudict-0.7a.utf8",
  f"{os.environ.get('DATA_DIR', 'data')}/cmudict-0.7a",
  f"{os.environ.get('DATA_DIR', 'data')}/cmudict.0.7a"
)

DICTIONARY_PATHS = (
  "/usr/share/dict/words",
  "/etc/dictionaries-common/words"
)

CMU_LINE = re.compile(r"([^ (]+)(?:\(([0-9]+)\))?  (.*)")

logging.basicConfig(format="%(module)s:%(lineno)s: %(levelname)s: %(message)s",
                    level=logging.INFO)
logger = logging.getLogger(__name__)

def first_path(*paths):
  "Return the first path that exists or None"
  for path in paths:
    if path is not None and os.path.exists(path):
      return path
  return None

def lines(path, encoding=None):
  "Read (line-number, line) from the given path"
  open_func = lambda path: open(path, "rt")
  if encoding is not None:
    open_func = lambda path: codecs.open(path, encoding=encoding)

  with open_func(path) as fobj:
    for lnr, line in enumerate(fobj):
      yield lnr, line.rstrip()

def parse_cmu_line(line, remove_stresses=False):
  """Parse a line out of the CMU dictionary.
  If remove_stresses is True, then stress indicators are removed. For example,
    CARING  K EH1 R IH0 NG
  becomes
    CARING  K EH R IH NG
  """
  match = CMU_LINE.match(line)
  if match is None:
    return None, None
  groups = match.groups()
  word, _, syl = None, None, None
  if len(groups) == 2:
    word, syl = groups
  elif len(groups) == 3:
    word, _, syl = groups
  else:
    return word, None
  syls = syl.split()
  if remove_stresses:
    syls = [syl.rstrip("0123456789") for syl in syls]
  return word, syls

def load_cmu(path, encoding=None, remove_stresses=False):
  "Load a CMU dictionary"
  results = collections.defaultdict(list)
  for lnr, line in lines(path, encoding=encoding):
    pos = "{}:{}".format(path, lnr)
    line = line.rstrip()
    # Skip comments
    if line.startswith(";;;"):
      continue
    # Skip invalid lines (shouldn't be any)
    if "  " not in line:
      logger.warning("%s: Line missing '  ': %r", pos, line)
      continue
    # Skip leading punctuation lines (which are duplicated later in the dict)
    if not 'A' <= line[0] <= 'Z':
      continue

    word, syls = parse_cmu_line(line, remove_stresses=remove_stresses)
    if word is None or syls is None:
      logger.error("%s: Failed to parse CMU line %r (got %s %s)", pos, line, word, syls)
      continue
    results[word].append(syls)

  logger.debug("Read %s words from %s", len(results), path)
  return results

def load_dict(path):
  """Load a text file of valid words, one word per line. Returns a dict. An
  empty dict is returned if the argument is None or if the path doesn't exist.
  The dictionary keys are upper-cased."""
  results = {}
  if path is not None and os.path.exists(path):
    for _, line in lines(path):
      results[line.upper()] = line
    logger.debug("Read %s words from %s", len(results), path)
  return results

def construct_rhyming_dict(cmu_dict=None, cmu_encoding=None, load_from=None, **kwargs):
  """Construct rhyme.RhymeDict instance.
  The RhymeDict object can be constructed via one of two methods: either from
  CMU dictionary or from JSON.

  When loading with a CMU dictionary, the following arguments are used:
    cmu_dict          Path to the CMU dictionary.
    cmu_encoding      CMU dictionary file encoding. If specified, the CMU
                      dictionary is loaded with the given encoding.
    remove_stresses   When True, remove syllable stress notation. This allows
                      rhymes across different syllable stresses.
    vowels="AEIOU"    Rhyming syllables are those starting with one of these
                      characters. Can be used to allow rhymes on stops,
                      plosives, etc.
  When loading from a JSON-encoded text file, the following arguments are used:
    load_from         Path to a JSON-encoded text file.
    vowels="AEIOU"    Rhyming syllables are those starting with one of these
                      characters. Can be used to allow rhymes on stops,
                      plosives, etc.
  """
  vowels = kwargs.get("vowels", "AEIOU")
  remove_stresses = kwargs.get("remove_stresses", False)
  if cmu_dict is None and load_from is None:
    # This case should normally be handled by the argument parser; this is a
    # fallback in case something slips by or someone calls this function
    # directly.
    raise ValueError("No dictionary to load!")

  if load_from is None:
    # Load manually
    rhymes = load_cmu(cmu_dict,
        encoding=cmu_encoding,
        remove_stresses=remove_stresses)
    robj = rhyme.RhymeDict(rhymes, vowels=vowels)
  else:
    # Load from json
    robj = rhyme.RhymeDict(load_from,
        vowels=vowels,
        entry_format=rhyme.RHYME_FORMAT_JSON)
  return robj

def main():
  ap = argparse.ArgumentParser(
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog="""
If -d,--cmudict is omitted, then the following paths are checked, in order:
  {cmu_paths}

Words not present in the English dictionary (see below) are printed in
upper-case.

If -D,--dict is omitted, then the following paths are checked, in order:
  {dict_paths}
Pass either -D="", --dict="", or --no-dict to disable dictionary loading.

Note that -a,--all and -n,--no-capital are ignored if no dictionary is loaded.

If -R,--remove-stresses is passed, then stress indication is removed from the
syllables read from the CMU dictionary. For example,
  CARING  K EH1 R IH0 NG
becomes
  CARING  K EH R IH NG
as the trailing numbers from "EH1" and "IH0" are removed. These numbers denote
the stressed syllables with a higher number indicating more intonation than a
lower number.

Pass -R,--remove-stresses to include rhymes differing in syllable stress. By
default, only perfect rhymes (ones that match syllables *and* syllable stress)
are displayed.
""".format(cmu_paths="\n  ".join(CMU_PATHS),
           dict_paths="\n  ".join(DICTIONARY_PATHS)))
  ap.add_argument("word", nargs="+",
      help="list words that rhyme with %(metavar)s")
  ap.add_argument("--profile", action="store_true", help="profile code")
  ap.add_argument("--profsort", metavar="KEY", default="time",
      help="sort profiler results by %(metavar)s (default: %(default)s)")
  ap.add_argument("--profdir", metavar="DIR", default=".",
      help="write profiler results to %(metavar)s (default: %(default)s)")

  ag = ap.add_argument_group("dictionary")
  ag.add_argument("-d", "--cmudict", metavar="PATH",
      help="path to the CMU dictionary (default: see --help)")
  ag.add_argument("-D", "--dict", metavar="PATH",
      help="text file with a list of allowable words, one per line")
  ag.add_argument("--no-dict", action="store_true",
      help="do not attempt to load any word dictionaries")
  ag.add_argument("-e", "--encoding", metavar="E", default="UTF-8",
      help="CMU file encoding (default: %(default)s)")
  ag.add_argument("-R", "--remove-stresses", action="store_true",
      help="remove stress indications from syllables (see below)")

  ag = ap.add_argument_group("saving/loading")
  ag.add_argument("-S", "--save", metavar="PATH",
      help="dump rhyming dictionary object to %(metavar)s")
  ag.add_argument("-L", "--load", metavar="PATH",
      help="load rhyming dictionary object from %(metavar)s")

  ag = ap.add_argument_group("output filtering")
  ag.add_argument("-a", "--all", action="store_true",
      help="include words not present in the words dictionary")
  ag.add_argument("-n", "--no-capital", action="store_true",
      help="omit words that start with an upper-case letter in the dictionary")

  ag = ap.add_argument_group("formatting")
  ag.add_argument("-w", "--wrap", metavar="N", type=int, default=-1,
      help="wrap output lines to at most %(metavar)s characters (-1 to disable)")
  ag.add_argument("-i", "--indent", metavar="N", default=4,
      help="indent resulting words by %(metavar)s spaces (default: %(default)s)")
  ag.add_argument("-s", "--sep", metavar="S", default="  ",
      help="separate resulting words by %(metavar)s (default: two spaces)")
  ag.add_argument("--inspect", action="store_true",
      help="dump internal information about the rhyming dictionary")
  ag.add_argument("-v", "--verbose", action="store_true", help="verbose mode")
  args = ap.parse_args()
  if args.verbose:
    logger.setLevel(logging.DEBUG)
    logging.getLogger("rhyme").setLevel(logging.DEBUG)

  cmu_path = first_path(args.cmudict, *CMU_PATHS)
  if cmu_path is None:
    ap.error("CMU dict not found; use -d,--cmudict")

  dict_path = first_path(args.dict, *DICTIONARY_PATHS)
  dictionary = None
  if dict_path is not None:
    dictionary = load_dict(dict_path)

  # The CMU dictionary is all in uppercase; do the same to simplify code
  words = [w.upper() for w in args.word]

  def should_include_word(word):
    "True if the word should be displayed, False otherwise"
    if dictionary is None:
      return True
    if args.all:
      return True
    entry = dictionary.get(word.upper(), "")
    if len(entry) == 0:
      return False
    if args.no_capital and entry[0] == entry[0].upper():
      return False
    return True

  if args.profile:
    def construct_func(*args, **kwargs):
      import cProfile
      with cProfile.Profile() as prof:
        rdict = construct_rhyming_dict(*args, **kwargs)
      prof.print_stats()
      return rdict
  else:
    construct_func = construct_rhyming_dict

  try:
    rhymedict = construct_func(
        cmu_dict=cmu_path,
        cmu_encoding=args.encoding,
        load_from=args.load,
        vowels="AEIOU",
        remove_stresses=args.remove_stresses)
  except UnicodeDecodeError as err:
    logger.error("Use -e,--encoding to specify an encoding for the CMU dictionary")
    raise err
  if args.inspect:
    rhymedict.inspect_to(None)
  if args.save is not None:
    rhymedict.save(args.save)

  def write_results(word, order, rhymes):
    "Write the word and its rhymes to stdout, wrapping long lines"
    logger.debug("%s: order=%s: %s", word, order, rhymes)
    kind = rhyme.RHYME_ORDER.get(order, "order {}".format(order))
    print("{} ({})".format(word, kind))
    line = " "*args.indent
    for idx, rword in enumerate(rhymes):
      if args.wrap != -1 and len(line) + len(args.sep) + len(rword) > args.wrap:
        print(line)
        line = " "*args.indent
      line += rword
      if idx+1 < len(rhymes):
        line += args.sep
    if line != " "*args.indent:
      print(line)

  for word in map(str.upper, args.word):
    if args.verbose:
      for vperf in rhymedict.pronunciation(word):
        logger.debug("%s: %s", word, vperf)
        for vord, vstr in rhymedict.perfects_of(vperf).items():
          logger.debug("Order %s: %s", vord, vstr)
    rhymes = {}
    for rhyme_order, rhyme_words in rhymedict.perfect(word):
      words = [word for word in rhyme_words if should_include_word(word)]
      words.sort()
      if dictionary is not None:
        words = [dictionary.get(word, word) for word in words]
      rhymes[rhyme_order] = words
      write_results(word, rhyme_order, words)
    print("")

if __name__ == "__main__":
  main()

# vim: set ts=2 sts=2 sw=2 et:
