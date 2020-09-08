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
import sys
import textwrap

import rhyme

CMU_PATHS = (
  "data/cmudict-0.7b.utf8",
  "data/cmudict-0.7b",
  "data/cmudict.0.7b",
  "data/cmudict-0.7a.utf8",
  "data/cmudict-0.7a",
  "data/cmudict.0.7a"
)

DICTIONARY_PATHS = (
  "/usr/share/dict/words",
  "/etc/dictionaries-common/words"
)

CMU_LINE = re.compile(r"([^ (]+)(?:\(([0-9]+)\))?  (.*)")

logging.basicConfig(format="%(module)s:%(lineno)s: %(levelname)s: %(message)s",
                    level=logging.INFO)
logger = logging.getLogger(__name__)

def lines(path, encoding=None):
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
  m = CMU_LINE.match(line)
  if m is None:
    return None, None
  g = m.groups()
  word, idx, syl = None, None, None
  if len(g) == 2:
    word, syl = g
  elif len(g) == 3:
    word, idx, syl = g
  else:
    return word, None
  syls = syl.split()
  if remove_stresses:
    syls = [syl.rstrip("0123456789") for syl in syls]
  return word, syls

def load_cmu(path, encoding=None, remove_stresses=False):
  results = collections.defaultdict(list)
  for lnr, line in lines(path, encoding=encoding):
    pos = "{}:{}".format(path, lnr)
    line = line.rstrip()
    # Skip comments
    if line.startswith(";;;"):
      continue
    # Skip invalid lines (shouldn't be any)
    if "  " not in line:
      logger.warning("Line missing '  ': {!r}".format(line))
      continue
    # Skip punctuation (which is duplicated later in the dict)
    if not 'A' <= line[0] <= 'Z':
      continue

    word, syls = parse_cmu_line(line, remove_stresses=remove_stresses)
    if word is None or syls is None:
      logger.error("Failed to parse CMU line {!r} (got {} {})".format(line, word, syls))
      continue

    results[word].append(syls)
  logger.debug("Read {} words from {}".format(len(results), path))
  return results

def load_dict(path):
  results = set()
  for lnr, line in lines(path):
    results.add(line.upper())
  logger.debug("Read {} words from {}".format(len(results), path))
  return results

def construct_rhyming_dict(cmu_dict=None, cmu_encoding=None, load_from=None, **kwargs):
  vowels = kwargs.get("vowels", "AEIOU")
  remove_stresses = kwargs.get("remove_stresses", False)
  if cmu_dict is None and load_from is None:
    # This case should normally be handled by the argument parser; this is a
    # fallback in case something slips by or someone calls this function
    # directly.
    raise ValueError("No dictionary to load!")
  if load_from is None:
    # Load manually
    rhymes = load_cmu(cmu_dict, encoding=cmu_encoding, remove_stresses=remove_stresses)
    robj = rhyme.RhymeDict(rhymes, vowels=vowels)
  else:
    # Load from json
    robj = rhyme.RhymeDict(load_from, vowels=vowels, entry_format=rhyme.RHYME_FORMAT_JSON)
  return robj

def main():
  ap = argparse.ArgumentParser(
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog="""
If -d,--cmudict is omitted, then CMU dictionaries are searched for in the
following locations. The first match is used.
  {cmu_paths}

Words not present in the English dictionary (see below) will be printed in
upper-case. Words present in the dictionary will be printed using the same case
as they appear in the dictionary.

If -D,--dict is omitted, then the following paths are examined. The first file
that exists is used.
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

Pass -R,--remove-stresses to include imperfect rhymes in the output. By
default, only perfect rhymes (ones that match syllables *and* syllable stress)
are displayed.
""".format(cmu_paths="\n  ".join(CMU_PATHS), dict_paths="\n  ".join(DICTIONARY_PATHS)))
  ap.add_argument("word", nargs="+",
      help="list words that rhyme with %(metavar)s")

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

  cmu_path = args.cmudict
  if cmu_path is None:
    for test_path in CMU_PATHS:
      if os.path.exists(test_path):
        cmu_path = test_path
        break
  if not os.path.exists(cmu_path):
    ap.error("{}: file not found; use -d,--cmudict".format(cmu_path))

  dict_path = args.dict
  if dict_path is None:
    for test_path in DICTIONARY_PATHS:
      if os.path.exists(test_path):
        dict_path = test_path
        break

  dictionary = None
  if dict_path is not None and os.path.exists(dict_path):
    dictionary = {}
    with open(dict_path, "rt") as fobj:
      for line in fobj:
        word = line.rstrip()
        dictionary[word.upper()] = word

  def should_include_word(word):
    "Return False to include the word in the final output"
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

  # The CMU dictionary is all in uppercase; do the same to simplify code
  words = [w.upper() for w in args.word]

  try:
    rhymedict = construct_rhyming_dict(
        cmu_dict=cmu_path,
        cmu_encoding=args.encoding,
        load_from=args.load,
        vowels="AEIOU",
        remove_stresses=args.remove_stresses)
  except UnicodeDecodeError as e:
    logger.error("Use -e,--encoding to specify an encoding for the CMU dictionary")
    raise e
  if args.inspect:
    rhymedict.inspect_to(None)
  if args.save is not None:
    rhymedict.save(args.save)

  def write_results(word, order, rhymes):
    logger.debug("{}: order={}: {}".format(word, order, rhymes))
    kind = "order {}".format(order)
    if order == 1:
      kind = "single"
    elif order == 2:
      kind = "double"
    elif order == 3:
      kind = "dactylic"
    print("{} ({})".format(word, kind))
    line = " "*args.indent
    for i, r in enumerate(rhymes):
      if args.wrap != -1 and len(line) + len(args.sep) + len(r) > args.wrap:
        print(line)
        line = " "*args.indent
      line += r
      if i+1 < len(rhymes):
        line += args.sep
    if line != " "*args.indent:
      print(line)

  for word in map(str.upper, args.word):
    if args.verbose:
      for vp in rhymedict.pronunciation(word):
        logger.debug("{}: {}".format(word, vp))
        for vo, vs in rhymedict.perfects_of(vp).items():
          logger.debug("Order {}: {}".format(vo, vs))
    rhymes = {}
    for rhyme_order, rhyme_words in rhymedict.perfect(word):
      logger.debug("Discovered {} rhymes (order {}) for {}".format(len(rhyme_words), rhyme_order, word))
      words = [w for w in rhyme_words if should_include_word(w)]
      words.sort()
      if dictionary is not None:
        words = [dictionary.get(w, w) for w in words]
      rhymes[rhyme_order] = words
      write_results(word, rhyme_order, words)
      #results = textwrap.wrap("  ".join(words), 40,
      #    initial_indent=" "*4, subsequent_indent=" "*4)
      #print("{} (order {})\n{}".format(word, rhyme_order, "\n".join(results)))
    print("")

if __name__ == "__main__":
  main()

# vim: set ts=2 sts=2 sw=2 et:
