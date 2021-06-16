from enum import Enum
import json

def resolve_path(path):
    return None

class Container:
    def __init__(self, data, parent=None):
        self.raw_content = data
        self.content = [Container(element, self) if type(element) == list else element for element in self.raw_content]
        self.parent = parent

        self.sub_containers = data[-1]
        if (special := self.sub_containers):
            self.name = special.get('#n')
            self.flags = special.get('#f', 0)
        else:
            self.name = None
            self.flags = 0
        self.count_visits = bool(self.flags & 1)
        self.track_turn_index = bool(self.flags & 2)
        self.count_start_only = bool(self.flags & 4)

class Divert:
    def __init__(self, data):
        pass

class Command:
    control_commands = {
        "ev"       : "Begin logical evaluation mode.",
        "/ev"      : "End logical evaluation mode.",
        "out"      : "The topmost object on the evaluation stack is popped and appended to the output stream (main story output).",
        "pop"      : "Pops a value from the evaluation stack, without appending to the output stream.",
        "->->"     : "Pop the callstack.",
        "~ret"     : "Pop the callstack.",
        "du"       : "Duplicate the topmost object on the evaluation stack.",
        "str"      : "Begin string evaluation mode.",
        "/str"     : "End string evaluation mode.",
        "nop"      : "No-operation.",
        "choiceCnt": "Pushes an integer with the current number of choices to the evaluation stack.",
        "turns"    : "Pops from the evaluation stack, expecting to see a divert target for a knot, stitch, gather or choice. Pushes an integer with the number of turns since that target was last visited by the story engine.",
        "visit"    : "Pushes an integer with the number of visits to the current container by the story engine.",
        "seq"      : "Pops an integer, expected to be the number of elements in a sequence that's being entered. In return, it pushes an integer with the next sequence shuffle index to the evaluation stack. This shuffle index is derived from the number of elements in the sequence, the number of elements in it, and the story's random seed from when it was first begun.",
        "thread"   : "Clones/starts a new thread, as used with the <- knot syntax in ink. This essentially clones the entire callstack, branching it.",
        "done"     : "Tries to close/pop the active thread, otherwise marks the story flow safe to exit without a loose end warning.",
        "end"      : "Ends the story flow immediately, closes all active threads, unwinds the callstack, and removes any choices that were previously created."
    }

    def __init__(self, command):
        pass

class Variable:
    def __init__(self, operation):
        pass

class Choice:
    def __init__(self, choice):
        pass

class ReadCount:
    def __init__(self, count):
        pass

with open('data.json', encoding='utf-8-sig') as f:
    data = json.load(f)
