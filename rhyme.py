#!/usr/bin/env python3

"""
Rhyming dictionary: supporting object.
"""

import collections
import json
import logging

import util

logging.basicConfig(format="%(module)s:%(lineno)s: %(levelname)s: %(message)s",
                    level=logging.INFO)
logger = logging.getLogger("rhyme")

RHYME_FORMAT_RAW = "raw"
RHYME_FORMAT_JSON = "json"

RHYME_ORDER = {
  1: "single",
  2: "double",
  3: "dactylic"
}

class RhymeDict:
  """Rhyming dictionary object.

  Internal data structure:
  entries: dict()
  table: dict()
    key: word (in all_words)
    value: list() of dict():
      "v": variant (number, 0..nr variants)
      "s": syllables (list/tuple of strings)
      "o": orders: list of pairs:
        (0, (<order-0 rhyme syllables>...))
        (1, (<order-1 rhyme syllables>...))...
  all_words: set() of known English words (uppercase)
  perfect: dict()
    key: space-delimited string of rhyming syllables
    value: list
  """
  def __init__(self,
               cmu_arg,
               #all_words=None,
               vowels="AEIOU",
               entry_format=RHYME_FORMAT_RAW):
    self._vowels = vowels
    self._entries = {}
    self._table = {}
    #self._all_words = all_words
    self._perfect = {}

    if entry_format == RHYME_FORMAT_RAW:
      self._entries = cmu_arg
      self._table = self._build_table()
      self._perfect = self._build_orders()
    elif entry_format == RHYME_FORMAT_JSON:
      self.load(cmu_arg)

  def save(self, fpath):
    "Write the parsed data structures to a file"
    data = {
      "entries": self._entries,
      "table": self._table,
      "perfect": self._perfect}
    with open(fpath, "wt") as fobj:
      json.dump(data, fobj)

  def load(self, fpath):
    "Load structures from a file"
    with open(fpath, "rt") as fobj:
      data = json.load(fobj)
    self._entries = data["entries"]
    self._table = data["table"]
    self._perfect = {int(k): v for k, v in data["perfect"].items()}
    logger.debug("Loaded %s entries", len(self._entries))
    logger.debug("Table: %s", len(self._table))
    for order in self._perfect:
      logger.debug("Perfect order %s: %s", order, len(self._perfect[order]))

  def inspect_to(self, to_file=None):
    "Log to logger (if to_file is None) or to_file"
    util.inspect_to("Vowels", self._vowels, to_file=to_file)
    util.inspect_to("Entries", self._entries, to_file=to_file)
    util.inspect_to("Table", self._table, to_file=to_file)
    #util.inspect_to("All Words", self._all_words, to_file=to_file)
    util.inspect_to("Perfect", self._perfect, to_file=to_file)

  def _build_table(self):
    "Build the internal data structure behind RhymeDict"
    table = collections.defaultdict(list)
    for word, variants in self._entries.items():
      for variant, syls in enumerate(variants):
        orders = tuple(self.perfects_of(syls).items())
        table[word].append({"v": variant, "s": syls, "o": orders})
    return table

  def _build_orders(self):
    "Build a table of perfect rhymes"
    # Build a structure containing all possible rhymes
    orders = collections.defaultdict(list)
    for word, variants in self._table.items():
      for vinfo in variants:
        vnr = vinfo["v"] # 1-index
        vsyls = vinfo["s"]
        vorders = vinfo["o"]
        for onr, vorder in vorders:
          orders[onr].append((vorder, {"w": word, "v": vnr, "s": vsyls}))

    # Build dicts, one per order, keyed by word's rhyme
    byorder = collections.defaultdict(dict)
    for onr, odefs in orders.items():
      if onr not in byorder:
        byorder[onr] = {}
      for odef in odefs:
        orhyme = odef[0]
        oinfo = odef[1]
        if orhyme not in byorder[onr]:
          byorder[onr][orhyme] = []
        byorder[onr][orhyme].append(oinfo["w"])

    for onr in byorder:
      nwords = 0
      for orhyme in byorder[onr]:
        owords = len(byorder[onr][orhyme])
        nwords += owords
      logger.debug("Order %s: %s total rhymes; %s total words", onr, len(byorder[onr]), nwords)

    return byorder

  def _perfects_order(self, order):
    return self._perfect.get(order, {})

  def _vowel(self, word):
    "True if word starts with a vowel"
    return word[0] in self._vowels

  def perfects_of(self, syls):
    "{order: rhyme_syls} for all perfect rhyme orders"
    vowels = [idx for idx, syl in enumerate(syls) if self._vowel(syl)]
    orders = {}
    for order, spos in enumerate(reversed(vowels)):
      orders[order+1] = " ".join(syls[spos:])
    return orders

  def pronunciation(self, word, variant=None):
    "Word pronunciation, either all variants or the numbered one"
    if word in self._entries:
      vstr = self._entries[word]
      if variant is None:
        return vstr
      if 1 <= variant <= len(vstr)+1:
        return vstr[variant-1]
      raise ValueError("Invalid variant {}; only {} exist".format(variant, len(vstr)))
    raise ValueError("{} not a known word".format(word))

  def perfect(self, word, order=None):
    """Return list of (rhyme_order, rhyme_words) for all perfect rhymes of the
    given word. If order is not None, then only the entries having
    rhyme_order == order are returned. Note that nothing may be returned if
    order is larger than the number of rhyming syllables in the word.
    """
    perfect_rhymes = collections.defaultdict(set)
    for variant in self.pronunciation(word):
      for vorder, rhyme_syls in self.perfects_of(variant).items():
        logger.debug("%s: order %s: %s", variant, vorder, rhyme_syls)
        if vorder not in self._perfect:
          logger.debug("No rhymes of order %s present", vorder)
          continue
        logger.debug("Candidates: %s", len(self._perfect[vorder]))
        if rhyme_syls in self._perfect[vorder]:
          rwords = set(self._perfect[vorder][rhyme_syls])
          # Words do not rhyme with themselves
          rwords.discard(word.upper())
          perfect_rhymes[vorder].update(rwords)

    results = {
        key: sorted(val) \
            for key, val in perfect_rhymes.items() \
            if len(val) > 0}
    if order is None:
      return results.items()
    if order in results:
      return [(order, results.values())]
    return []

  def consonant_perfect(self, word, oder=None):
    """Return a list of (rhyme_order, rhyme_words) for all consonant-perfect
    rhymes of the given word. If order is not None, then only the entries
    having rhyme_order == order are returned.

    "Consonant-perfect" rhymes are (in this particular program) perfect rhymes
    that also share the same syllable immediately before the rhyming syllable.
    For example, "children" and "warden".
    """
    raise NotImplementedError("TODO")

# vim: set ts=2 sts=2 sw=2 et:
