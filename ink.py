import json

class Story:
    def __init__(self, jdata):
        self.version = jdata.get('inkVersion')
        self.root = Container(jdata.get('root', {}))
        self.list_defs = jdata.get('listDefs')

class Container:
    def __init__(self, data, parent=None, name=None): # TODO: Track stack and use to make contents more useful
        self.raw_contents = data
        self.contents = [Container(element, self) if type(element) == list else parse_object(element, self) for element in self.raw_contents[:-1]]
        self.parent = parent

        self.sub_elements = {}
        if data[-1]:
            self.name = name or data[-1].get('#n')
            self.flags = data[-1].get('#f', 0)
            for name, container in data[-1].items():
                if name in ['#n', '#f']: # Don't try to create containers for the special keys #n and #f
                    continue
                self.sub_elements[name] = Container(container, self, name)
        else:
            self.name = name
            self.flags = 0
        self.count_visits = bool(self.flags & 1)
        self.track_turn_index = bool(self.flags & 2)
        self.count_start_only = bool(self.flags & 4)

    def __repr__(self):
        ret = f'Container: {self.name or "(unnamed)"}'
        if self.sub_elements:
            ret += f' ({len(self.sub_elements)} sub-element(s))'
        
        return ret

    def __getattr__(self, attr):
        if attr not in self.__dict__:
            try:
                value = self.__dict__['sub_elements'][attr]
                self.__dict__[attr] = value
            except KeyError:
                raise AttributeError
            return self.__dict__[attr]

class Path:
    def __init__(self, path):
        self.path = path
        self.components = path.split('.')
    
    def is_relative(self):
        return self.path.startswith('.')
    
    def __repr__(self):
        return f'{"Relative" if self.is_relative() else "Absolute"} Path: {self.path}'

class Divert:
    def __init__(self, data: dict, container: Container):
        self.raw = data
        if '->' in data:
            self.path = data["->"]
            if 'var' in data:
                self.path = Path(self.path)
                self.type = "Variable divert"
            else:
                self.type = "Standard divert"
        elif "f()" in data:
            self.path = Path(data["f()"])
            self.type = "Function call"
        elif "->t->" in data:
            self.path = Path(data["->t->"])
            self.type = "Tunnel"
        elif "x()" in data:
            self.path = data["x()"]
            self.type = "External function"
        else:
            self.type = "Unknown"
            self.path = ""
        
        self.conditional = data.get('c')
        
        if type(self.path) == Path:
            #self.target = Divert.resolve_path(self.path, container)
            pass

    def __repr__(self):
        return f'{self.type}: {self.path}{" (conditional)" if self.conditional else ""}'

    # TODO: takes a path, root container, and starting position and returns the element referenced.
    @classmethod
    def resolve_path(path: Path, start: Container):
        if path.is_relative():
            return None
        else:
            parent = start
            try:
                while True:
                    parent = parent.parent
            except AttributeError:
                pass
            return None

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
        "turn"     : "Turns",
        "readC"    : "ReadCount",
        "srnd"     : "Seeds the RNG",
        "visit"    : "Pushes an integer with the number of visits to the current container by the story engine.",
        "seq"      : "Pops an integer, expected to be the number of elements in a sequence that's being entered. In return, it pushes an integer with the next sequence shuffle index to the evaluation stack. This shuffle index is derived from the number of elements in the sequence, the number of elements in it, and the story's random seed from when it was first begun.",
        "thread"   : "Clones/starts a new thread, as used with the <- knot syntax in ink. This essentially clones the entire callstack, branching it.",
        "done"     : "Tries to close/pop the active thread, otherwise marks the story flow safe to exit without a loose end warning.",
        "end"      : "Ends the story flow immediately, closes all active threads, unwinds the callstack, and removes any choices that were previously created.",
        "void"     : "Places an object on the evaluation stack when a function returns without a value.",
        "listInt"  : "ListFromInt",
        "range"    : "ListRange",
        "lrnd"     : "ListRandom",
    }

    def __init__(self, command):
        self.command = command
        self.description = Command.control_commands.get(command)

    def __repr__(self):
        return f'Command: {self.command}'

    def __str__(self):
        return f'{self.command} - {self.description}'

class Variable:
    def __init__(self, operation):
        assert type(operation) == dict
        self.reassignment = operation.get('re', False)
        try:
            self.target = operation['VAR=']
            self.operation = 'Set'
        except KeyError:
            try:
                self.target = operation['temp=']
                self.operation = 'Set'
            except KeyError:
                try:
                    self.target = operation['VAR?']
                    self.operation = 'Get'
                except KeyError:
                    try:
                        self.target = operation['^var']
                        self.operation = 'Pointer'
                    except KeyError:
                        raise ValueError(f'Unknown operation for given dict {operation}')

    def __repr__(self):
        s = f'{self.operation} {self.target}'
        if self.operation == 'Set':
            s += f' ({"reassignment" if self.reassignment else "new"})'
        return s

    def __str__(self):
        s = f'{self.operation} {self.target} from stack'
        if self.operation == 'Set':
            s += f' ({"reassignment" if self.reassignment else "new"})'
        return s

class NativeFunctionCall:
    native_functions = {
        ('+', 'x.Union(y)'),
        ('-', 'x - y'),
        ('CEILING', '(float)Math.Ceiling((double)x)'),
        ('>=', 'x >= y'),
        ('/', 'x / y'),
        ('+', 'x + y'),
        ('<', 'x < y'),
        ('LIST_INVERT', 'x.inverse'),
        ('>', 'x > y'),
        ('||', 'x != 0f || y != 0f'),
        ('==', 'x.Equals(y)'),
        ('||', 'x.Count > 0 || y.Count > 0'),
        ('FLOOR', '(float)Math.Floor((double)x)'),
        ('!=', '!x.Equals(y)'),
        ('&&', 'x != 0 && y != 0'),
        ('LIST_COUNT', 'x.Count'),
        ('?', 'x.Contains(y)'),
        ('!', 'x == 0'),
        ('&&', 'x != 0f && y != 0f'),
        ('INT', '(int)x'),
        ('%', 'x % y'),
        ('MIN', 'Math.Min(x, y)'),
        ('!', 'x == 0f'),
        ('<', 'x.LessThan(y)'),
        ('*', 'x * y'),
        ('_', '-x'),
        ('&&', 'x.Count > 0 && y.Count > 0'),
        ('<=', 'x.LessThanOrEquals(y)'),
        ('LIST_ALL', 'x.all'),
        ('>=', 'x.GreaterThanOrEquals(y)'),
        ('||', 'x != 0 || y != 0'),
        ('>', 'x.GreaterThan(y)'),
        ('==', 'x == y'),
        ('LIST_MIN', 'x.MinAsList()'),
        ('LIST_MAX', 'x.MaxAsList()'),
        ('!=', 'x != y'),
        ('LIST_VALUE', 'x.maxItem.Value'),
        ('!?', '!x.Contains(y)'),
        ('!', '(x.Count == 0) ? 1 : 0'),
        ('POW', '(float)Math.Pow((double)x, (double)y)'),
        ('-', 'x.Without(y)'),
        ('MAX', 'Math.Max(x, y)'),
        ('<=', 'x <= y'),
        ('^', 'x.Intersect(y)'),
        ('FLOAT', '(float)x')
    }
    native_functions = [
        '+',
        '-',
        '*',
        '/',
        '>',
        '<',
        '>=',
        '<=',
        '==',
        '!=',
        '?', # Contains
        '!',
        '%',
        '_', # Negation
        '^', # Intersection
        '||',
        '&&',
        '!?', # Does not contain
        'CEILING',
        'FLOOR',
        'INT',
        'FLOAT',
        'POW',
        'MIN',
        'MAX',
        'LIST_INVERT', # Ink list inverse
        'LIST_ALL',
        'LIST_VALUE',
        'LIST_MIN',
        'LIST_MAX',
        'LIST_COUNT'
    ]

    def __init__(self, operation):
        self.operation = operation
    
    def __repr__(self):
        return self.operation

class Choice:
    def __init__(self, choice):
        pass

class ReadCount:
    def __init__(self, data):
        self.path = data['CNT?']

    def __repr__(self):
        return f'Read count: {self.path}'

class InkList:
    def __init__(self, data):
        self.origins = data.get('origins')
        self.data = data.get('list')
    
    def __repr__(self): # TODO more useful repr
        return repr(self.data)

class Glue:
    def __init__(self, data):
        pass

    def __repr__(self):
        return 'Glue'

def parse_object(object, container):
    try:
        obj_type = get_type(object)
    except ValueError as e:
        print(e)
    try:
        if obj_type == Divert:
            return Divert(object, container)
        return obj_type(object)
    except:
        print(f'error parsing object {object}')

# takes any object and returns the most likely type
def get_type(object):
    if type(object) in (int, float, bool):
        return type(object)
    elif type(object) == str:
        if object == '\n' or object.startswith('^'):
            return str
        elif object == '<>':
            return Glue
        elif object == 'L^':
            return Command
        elif object in Command.control_commands:
            return Command
        elif object in NativeFunctionCall.native_functions:
            return NativeFunctionCall
    if type(object) == list:
        return Container
    elif type(object) == dict:
        if any([key in object for key in ['^var', 'VAR=', 'temp=', 'VAR?']]):
            return Variable
        elif 'CNT?' in object:
            return ReadCount
        elif any([key in object for key in ['^->', '->', 'f()', '->t->', 'x()']]):
            return Divert
        elif '*' in object and 'flg' in object:
            return Choice
        elif 'list' in object:
            return InkList
        else:
            print(f'unknown dict {object}')
            raise ValueError(f'unknown dict {object}')
    else:
        print(f'unknown object type - {object}')
        return ValueError(f'unknown object type - {object}')


with open('data.json', encoding='utf-8-sig') as f:
    data = json.load(f)
