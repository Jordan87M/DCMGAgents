from DCMGClasses.resources.math import interpolation
from DCMGClasses.CIP import wrapper

class Resource(object):
    
    def __init__(self,owner,**kwargs):
        self.owner = owner
        
    def setOwner(self,newOwner):
        print("transferring ownership of {resource} from {owner} to {newowner}".format(resource = self, owner = self.owner, newowner = newOwner))
        self.owner = newOwner

class Storage(Source):
    
    def __init__(self,owner,dischargePower,chargePower,capacity,chargeChannel,dischargeChannel,soc,**kwargs):
        super(Storage,self).__init__(self,owner,dischargePower,dischargeChannel,**kwargs)
        self.chargePower = chargePower
        self.capacity = capacity
        self.chargeChannel = chargeChannel
        self.soc = soc
        
        ChargeChannel = Channel(chargeChannel)
        
    def charge(self,setpoint):
        pass
    
class LeadAcidBattery(Storage):
    SOCtable = [(0, 11.8),(.25, 12.0),(.5, 12.2),(.75, 12.4),(1, 12.7)]
    def __init__(self,owner,dischargePower,chargePower,capacity,chargeChannel,dischargeChannel,**kwargs):
        super(LeadAcidBattery,self).__init__(self,owner,dischargePower,chargePower,capacity,chargeChannel,dischargeChannel,soc,**kwargs)
        
        
        
    def getSOC(self):
        #get SOC from PLC
        pass
    
    def getSOCfromOCV(self):
        #get battery voltage from PLC
        tagname = "SOURCE_{num}_REG_VOLTAGE".format(num = self.DischargeChannel.channelNumber)
        voltage = getTagValue(tagName)
        soc = lininterp(self.SOCtable,voltage)
        return soc
    
class Source(Resource):
    def __init__(self,owner,dischargePower,dischargeChannel,**kwargs):
        super(Source,self).__init__(self,owner)
        self.dischargePower = dischargePower
        self.dischargeChannel = dischargeChannel
        
        DischargeChannel = Channel(dischargeChannel)
        
    def getInputUnregVoltage(self):
        voltage = self.DischargeChannel.getUnregV()
        return voltage
    
    def getOutputRegVoltage(self):
        voltage = self.DischargeChannel.getRegV()
        return voltage
        
    def getInputUnregCurrent(self):
        current = self.DischargeChannel.getUnregI()
        return current
        
    def getOutputUnregCurrent(self):
        current = self.DischargeChannel.getRegI()
        return current
    
    def connectSource(self,mode,setpoint):
        pass
    
    def disconnectSource(self):
        pass
    
        
class SolarPanel(Source):
    def __init__(self,owner,dischargePower,dischargeChannel,Voc,Vmpp,**kwargs):
        super(SolarPanel,self).__init__(self,owner,dischargePower,dischargeChannel,**kwargs)
        self.Voc = Voc
        self.Vmpp = Vmpp
        
    def powerAvailable(self):
        pass
        
    
class Channel():
    def __init__(self,channelNumber):
        self.channelNumber = channelNumber
        
    def getRegV(self):
        tagName = "SOURCE_{d}_REG_VOLTAGE".format(d = self.channelNumber)     
        #call to CIP wrapper
        value = getTagValue(tagName)
        return value   
        
    def getUnregV(self):
        tagName = "SOURCE_{d}_UNREG_VOLTAGE".format(d = self.channelNumber)
        value = getTagValue(tagName)
        return value
    
    def getRegI(self):
        tagName = "SOURCE_{d}_REG_CURRENT".format(d = self.channelNumber)
        value = getTagValue(tagName)
        return value
    
    def getUnregI(self):
        tagName = "SOURCE_{d}_UNREG_CURRENT".format(d = self.channelNumber)
        value = getTagValue(tagName)
        return value
    
        