import numpy as np
from collections import OrderedDict

class GenerationFileParser:

    def __init__(self, filename, id):
        self.nameToColumnMap = {}
        self.filename = filename
        self.id = id
        self.row_id = 0 #row corresponding to id
        
        self.numVariab = 0 #number of variables
        self.buildNameToColumnMap()
        self.numIndividuals = 0  #numbers of lines
        self.numValues = len(self.nameToColumnMap)  #number of columns
        self.readData()


    def rows(self):
        sim_str = []

        idx_col = 0
        sim_str.append(" ID=" + self.id)
        
        for idx_col in range(self.numValues-self.numVariab):
            data = self.data[self.row_id, self.numVariab+idx_col]
            name = self.nameToColumnMap.keys()[self.numVariab+idx_col]
            sim_str.append(name + "=" + str(data))
            #row = Individual(self.data[id, self.numVariab+idx_col],self.nameToColumnMap.keys()[self.numVariab+idx_col])
            #yield row

        return " ".join(sim_str)


    def cols(self):
        for name, idx in self.nameToColumnMap.items():
            col = Variable(self.data[:, idx], name)
            yield col


    def buildNameToColumnMap(self):
        data_format = open(self.filename, "r").readlines()[0]
        formats = str.split(data_format, ",")

        col_idx = 0
        
        for col_name in formats:
            col_name.lstrip().rstrip()
            col_name = col_name.replace('\n', '')
            col_name = col_name.rstrip()
            col_name = col_name.lstrip("%")
            if col_name.startswith(' DVAR'):
                self.numVariab = col_idx
                col_name =col_name.lstrip(' DVAR: %')
            self.nameToColumnMap[col_name] = col_idx    
            col_idx += 1

        self.nameToColumnMap = OrderedDict(sorted(self.nameToColumnMap.items(), key=lambda x: x[1]))

    def readData(self):

        lines = open(self.filename,"r").readlines()
        self.numIndividuals = len(lines) - 1

        self.data = np.zeros((self.numIndividuals, self.numValues))

        i = 0
        for line in lines:
            if line.startswith('%'):
                continue
            j = 0
            vals = str.split(line.strip(), ' ')
            for val in vals:
                if j == 1: 
                    self.data[i, j] = float(val)
                else:
                    self.data[i, j] = float(val)
                    #self.data[i,j] = float('{:+E}'.format(float(val)))
                  
                if (self.data[i, 0] == float(self.id)):
                    self.row_id = i

                j += 1

            i += 1


    def replaceHeader(self, new_header):

        f = open(self.filename, 'r')
        lines = f.readlines()
        lines[0] = new_header
        f.close()

        f = open(self.filename, 'w')
        for line in lines:
            f.write(line)
        f.close()

class Individual:

    def __init__(self, data, names):
        self.data  = data
        self.names = names

    def toString(self):
        return ""

    def toSimulationString(self):

        sim_str = []

        #for name, col_idx in self.names.items():
           # name = name.lstrip("%")
            #sim_str.append(self.names + "=" + str(self.data))

        #return " ".join(sim_str)


class Variable:

    def __init__(self, data, name):
        self.data = data
        self.name = name

    def min(self):
        return min(self.data)

    def max(self):
        return max(self.data)
