import time

class DataSeries(object):
    def __init(self,signalname,pathname):
        try:
            #make directories on path
            os.makedirs(pathname)
            self.signalname = signalname
            self.pathname = pathname + "{sig}.csv".format(sig = self.signalname)
            #create file, truncating if it exists
            file = open(self.pathname,'r')
            file.close()
            
            self.bufsize = 10
            self.length = 0
            self.buffer = [0] * self.bufsize
            self.bufptr = 0
            
            self.rollingavg = 0
            self.avg = 0
        except Exception as e:
            print(e)
            
            
    def addPoint(self,value):
        try:
            file = open(self.pathname,'a')
            #write to file here
            file.write("{val}, {time}\n".format(val = value, time.time()))
            file.close()
            #write to buffer here
            
            self.length += 1
            self.bufptr += 1
            if self.bufptr > 9:
                self.bufptr = 0
            old = self.buffer[self.bufptr]
            self.buffer[self.bufptr] = value
            
            #update averages
            self.rollingavg += ((value - old)/self.bufsize)
            if self.length == 1:
                self.avg = value
            else:
                self.avg = ((self.length-1)/self.length)*(self.avg + value)
            
        except IOError as e:
            print("couldn't open file")
        
            
class StatsBase(object):
    def __init__(self):
        self.logpathbase = "~/volttron/ugridlogs/"
        self.timeseries = {}
        
    def addNewSeries(self,signalname,pathname):
        self.timeseries[signalname] = DataSeries(signalname,pathname)
    
    
 
class HomeownerStats(StatsBase):
    def __init__(self,homename):
        super(self,HomeownerStats).__init__()
        self.homename = homename
        self.logpathagent = self.logpathbase + "{path}/".format(path = homename)
        
        