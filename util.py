#!/usr/bin/env python3

import logging
import os
import six
import sys

import cProfile
import pstats

logging.basicConfig(format="%(module)s:%(lineno)s: %(levelname)s: %(message)s",
                    level=logging.INFO)
logger = logging.getLogger("rhyme-util")

class ProfileCall(object):
  def __init__(self, sort_key=None, out_path=None, out_name=None):
    self._pr = None
    self._sort = sort_key
    self._path = out_path
  def __enter__(self):
    self._pr = cProfile.Profile()
    self._pr.enable()
  def __exit__(self, *exc_info):
    self._pr.disable()
    stats = pstats.Stats(self._pr)
    if self._sort is not None:
      stats.sort_stats(self._sort)
    if self._path is not None:
      stats.dump_stats(self._path)
    else:
      stats.print_stats()

def inspect_to(oname, obj, to_file=None):
  "Inspect a named value to either the logger or a file object"
  def write(line):
    if to_file is None:
      logger.info("{}: {}".format(oname, line.rstrip("\n")))
    else:
      to_file.write("{}: {}\n".format(oname, line.rstrip("\n")))

  if obj is None:
    write("{}: None".format(oname))
    return

  def ellipses(o, l=80):
    r = str(o)
    if len(r) > l:
      r = r[:l-3] + "..."
    return r
  def typename(o):
    otype = type(o)
    if otype == collections.defaultdict:
      otype = dict
    return otype.__name__ if hasattr(otype, "__name__") else str(otype)

  def count_types(seq, as_str=False):
    counts = {}
    for item in seq:
      tname = typename(item)
      counts[tname] = counts.get(tname, 0) + 1
    results = sorted(counts.items(), key=lambda ab: ab[1])
    if as_str:
      return ", ".join("{}:{}".format(a, b) for a, b in results)
    return results

  otype = type(obj)
  if otype == collections.defaultdict:
    otype = dict
  tname = typename(obj)

  if tname in ("int", "long", "str", "unicode", "bytes"):
    write("{}[{}]: {}".format(tname, len(obj), ellipses(obj)))
  elif otype in (tuple, list, set):
    typecounts = count_types(obj, as_str=True)
    write("{}[{}] of {}: {}".format(tname, len(obj), typecounts, ellipses(obj)))
  elif otype == dict:
    keycounts = count_types(obj.keys(), as_str=True)
    valcounts = count_types(obj.values(), as_str=True)
    write("{}[{}]:".format(tname, len(obj)))
    write("  keys={}, values={}, {}".format(keycounts, valcounts, ellipses(obj)))
  else:
    write(ellipses(obj))
  return

# vim: set ts=2 sts=2 sw=2:
