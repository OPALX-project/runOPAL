from PathNameGenerator import PathNameGenerator
from decimal import Decimal
from ast import literal_eval
import sys
"""
OpalDictionary class

@author: Andreas Adelmann <andreas.adelmann@psi.ch>
@author: Yves Ineichen
@version: 0.1
"""
class OpalDict:

    def __init__(self, template):
        self.dict = {}
        self.rangevars = {}
        self.uservars = []
        self.numRanges = 0

        self.path_name_generator = PathNameGenerator()
        self.fillDictionary(template)

    def __iter__(self):
        return self.dict.__iter__()

    def __setitem__(self, key, value):
        scalevars = {}
        scalevars['GUNSOLB'] =  1.0

        try:
            self.dict[key] = value * scalevars[key]
        except KeyError:
            self.dict[key] = value

    def __getitem__(self, key):
        return self.dict[key]

    def items(self):
        return self.dict.items()

    def fillDictionary(self, fileName):
        fp = open(fileName,"r")
        for line in fp:
            if not line == "\n":
                li = line.strip()
                if not li.startswith("#"):
                    aline = line.split("#")[0]
                    name,val = aline.split()
                    self.dict[name.rstrip()] = val.lstrip().rstrip()
        fp.close()

    def dumpMapping(self):
        mapping = str(self.path_name_generator)
        if len(mapping) > 0:
            f = open('name_mapping', 'w')
            f.write(mapping)
            f.close()

    def generateDirectoryName(self):
        dirname = ""
        for p in self.uservars:
            dirname += "_" + str(p[0]) + "=" + str(p[1])
        for (k, v) in self.rangevars.items():
            dirname += "_" + str(k) + "=" + str(self.dict[k])
        return self.path_name_generator.compress(dirname)

    def scaleDictVar(self, var, scaleWith):
        if var in self.dict:
        #if self.dict.has_key(var):
            self.dict[var] = float(self.dict[var])*scaleWith

    def getType(self,s):
        try:
            return int(s)
        except ValueError:
            return float(s)

    def hasRanges(self):
        return self.numRanges > 0

    def Range(self):
        return self.rangevars

    def scale(self):
        self.scaleDictVar('GUNSOLB', 1.)

    def addUserValues(self, argv):
        for arg in argv:
            if arg.find("=") > 0:
                
                data = str(arg.split(" "))        # arguments are separated by spaces            
                eqsidx = data.find("=")           # idx of = 
                var = data[2:eqsidx]
                rhs = data[eqsidx+1:len(data)-2]

                if var in self.dict:
                #if self.dict.has_key(var):
                    #check if we have a range
                    if rhs.find(':') > 0:
                        range = rhs.split(":")
                        if len(range) == 3:
                            rvar = []
                            for r in range:
                                rvar.append(self.getType(r))
                            self.rangevars[var] = rvar
                            self.numRanges = self.numRanges + 1
                        else:
                            print( "OpalDict: Range has to be of the form from:to:step!")
                            sys.exit(1)
                    else:
                        try:
                            val = literal_eval(rhs)
                            if (isinstance(val, int) or isinstance(val, float)):
                                self.uservars.append( (var, Decimal(rhs)) )
                                self.dict[var] = Decimal(rhs) #self.getType(rhs)
                        except: # add string
                            self.uservars.append( (var, rhs) )
                            self.dict[var] = rhs
                else:
                    if var.find("--") < 0: # not a regular option
                        print( 'OpalDict: Key (' + var + ')not found can not add to dictionary, check the OPAL template file')
                        sys.exit(1)
