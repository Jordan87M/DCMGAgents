from datetime import datetime, timedelta

from DCMGClasses.CIP import tagClient
from __builtin__ import False

class CustomerProfile(object):
    def __init__(self,name,location,resources,priorityscore,**kwargs):
        self.name = name
        self.location = location
        self.resources = resources
        self.Resources = []
        self.tagCache = {}
        #permission to connect to grid
        self.permission = False
        
        self.priorityscore = priorityscore
        
        loclist = self.location.split('.')
        if type(loclist) is list:
            if loclist[0] == "DC":
                self.grid, self.branch, self.bus, self.load = loclist
                if loclist[1] == "MAIN":
                    pass
                else:
                    self.branchNumber = self.branch[-1]
                    self.busNumber = self.bus[-1]
                    self.loadNumber = self.load[-1]
            elif loclist[0] == "AC":
                pass
        else:
            print("the first part of the location path should be AC or DC")
        
        self.customerAccount = Account(self.name,0.0)
        self.DRenrollee = False
        
        #tag names
        self.relayTag = "BRANCH_{branch}_BUS_{bus}_LOAD_{load}_User".format(branch = self.branchNumber, bus = self.busNumber, load = self.loadNumber)
        self.currentTag = "BRANCH_{branch}_BUS_{bus}_LOAD_{load}_Current".format(branch = self.branchNumber, bus = self.busNumber, load = self.loadNumber)
        self.voltageTag = "BRANCH_{branch}_BUS_{bus}_Voltage".format(branch = self.branchNumber, bus = self.busNumber)
        self.powerTag = "BRANCH_{branch}_BUS_{bus}_LOAD_{load}_Power".format(branch = self.branchNumber, bus = self.busNumber, load = self.loadNumber)

    def addResource(self,res):
        res.owner = self
        self.Resources.append(res)
        
        
    #change maximum power draw for a customer
    def updateService(self,amount):
        self.maxDraw = amount
            
    def disconnectCustomer(self):
        tagClient.writeTags([self.relayTag],[False])
        
    def connectCustomer(self):
        tagClient.writeTags([self.relayTag],[True])
        
    def measureVoltage(self):
        tag = self.voltageTag
        tagval = tagClient.readTags([tag])
        self.tagCache[tag] = (tagval, datetime.now())
        return tagval
    
    def measureCurrent(self):
        tag = self.currentTag
        tagval = tagClient.readTags([tag])
        self.tagCache[tag] = (tagval, datetime.now())
        return tagval
    
    def measurePower(self):
        tagvals = tagClient.readTags([self.currentTag, self.voltageTag])
        power = tagvals[self.currentTag]*tagvals[self.voltageTag]
        self.tagCache[self.powerTag] = (power, datetime.now())
        return power
            
    
    '''calls measureCurrent only if cached value isn't fresh'''    
    def getCurrent(self,threshold = 5.1):
        tag = self.currentTag
        val, time = self.tagCache.get(tag,(None, None))
        if val is not None and time is not None:
            diff = datetime.now() - time
            et = diff.total_seconds()    
                    
            if et < threshold:
                return val        
        return measureCurrent()
    
    '''calls measureVoltage only if cached value isn't fresh'''
    def getVoltage(self,threshold = 5.1):
        tag = self.voltageTag
        val, time = self.tagCache.get(tag,(None, None))
        if val is not None and time is not None:
            diff = datetime.now() - time
            et = diff.total_seconds()
            
            if et < threshold:
                return val
            
        return measureVoltage()
    
    '''calls measurePower only if cached value isn't fresh'''
    def getPower(self,threshold = 5.1):
        val, time = self.tagCache.get(self.powerTag,(None, None))
        if val is not None and time is not None:
            diff = datetime.now() - time
            et = diff.total_seconds()
            
            if et < threshold:
                return val
            
        return measurePower()
    
    def printInfo(self, depth = 0):
        spaces = '    '
        print(spaces*depth + "CUSTOMER: {name} is a {type}".format(name = self.name, type = self.__class__.__name__))
        print(spaces*depth + "LOCATION: {loc}".format(loc = self.location))
        print(spaces*depth + "RESOURCES:")
        for res in self.Resources:
            res.printInfo(depth + 1)
            
class ResidentialCustomerProfile(CustomerProfile):
    def __init__(self,name,location,resources,priorityscore,**kwargs):
        super(ResidentialCustomerProfile,self).__init__(name,location,resources,priorityscore,**kwargs)
        self.maxDraw = 3
        self.rateAdjustment = 1
        
        
class CommercialCustomerProfile(CustomerProfile):
    def __init__(self,name,location,resources,priorityscore,**kwargs):
        super(CommercialCustomerProfile,self).__init__(name,location,resources,priorityscore,**kwargs)
        self.maxDraw = 6
        self.rateAdjustment = 1
        
class Account(object):
    def __init__(self,holder,initialBalance = 0):
        self.holder = holder
        self.accountBalance = initialBalance
        
    def adjustBalance(self,amount):
        self.accountBalance += amount
        
        
class ResourceProfile(object):
    def __init__(self,**res):
        self.owner = res["owner"]
        self.capCost = res["capCost"]
        self.location = res["location"]
        self.name = res["name"]
        
        self.dischargeChannelNumber = res["dischargeChannel"]
        
        self.state = None
        self.setpoint = None
        
        self.dischargeVoltageTag = "SOURCE_{d}_RegVoltage".format(d = self.dischargeChannelNumber)
        self.dischargeCurrentTag =  "SOURCE_{d}_RegCurrent".format(d = self.dischargeChannelNumber)
        
        
        
    def getDischargeCurrent(self):
        return tagClient.readTags([self.dischargeCurrentTag])
    
    def getDischargeVoltage(self):
        return tagClient.readTags([self.dischargeVoltageTag])
        
    def getDischargePower(self):
        power = self.getDischargeCurrent()*self.getDischargeVoltage()
        return power
            
    def setOwner(self,newOwner):
        self.owner = newOwner
        
    def printInfo(self, depth = 0):
        spaces = '    '
        print(spaces*depth + "RESOURCE: {name} is a {type}".format(name = self.name, type = self.__class__.__name__))
        print(spaces*depth + "LOCATION: {loc}".format(loc = self.location))

class SourceProfile(ResourceProfile):
    def __init__(self,**res):
        super(SourceProfile,self).__init__(**res)
        self.maxDischargePower = res["maxDischargePower"]
       
    def getChargePower(self):
        return 0
    
class StorageProfile(SourceProfile):
    def __init__(self,**res):
        super(StorageProfile,self).__init__(**res)
        self.maxChargePower = res["maxChargePower"]
        self.capacity = res["capacity"]
        
        self.chargeChannelNumber = res["chargeChannel"]
        
        self.chargeVoltageTag = "SOURCE_{d}_UnregVoltage".format(d = self.chargeChannelNumber)
        self.chargeCurrentTag = "SOURCE_{d}_UnregCurrent".format(d = self.chargeChannelNumber)
        

    def getChargeCurrent(self):
        return tagClient.readTags([self.chargeCurrentTag])
    
    def getChargeVoltage(self):
        return tagClient.readTags([self.chargeVoltageTag])
        
    def getChargePower(self):
        return self.getChargeCurrent() * self.getChargeVoltage()

class SolarProfile(SourceProfile):
    def __init__(self,**res):
        super(SolarProfile,self).__init__(**res)
        
class LeadAcidBatteryProfile(StorageProfile):
    def __init__(self,**res):
        super(LeadAcidBatteryProfile,self).__init__(**res)
        
class GeneratorProfile(SourceProfile):
    def __init__(self,**res):
        super(GeneratorProfile,self).__init__(**res)
        
        