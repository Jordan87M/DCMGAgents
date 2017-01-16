import socket
import sys
import subprocess

def startTagServer():
    try:
        subprocess.call(["~/Downloads/TagServer/prod/ServeTagsTemporarily&"],shell = True)
    except Exception as e:
        print(e.args)
        print("problem starting tag server")
        

'''writes multiple tags to a tag server. tag names and values must be provided as lists
even if only a single tag value pair is being written'''
def writeTags(names,values,plc = "user"):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tserver_addr = ('localhost',12897)
    print("tag client attempting to connect and write to {host}:{port}".format(host = tserver_addr[0], port = tserver_addr[1]))
    
    try:
        sock.connect(tserver_addr)
        
        message = "write {plc}".format(plc = plc)
        for index,name in enumerate(names):
            message = message + " {name}:{value}".format(name = name, value = str(values[index]))
        message = message + "\n"
        sock.sendall(message)
        
        data = sock.recv(1024)
        print("tag client received: {info}".format(info = data))
            
    except Exception:
        print("tag client experiencing problem")
    finally:
        print("closing tag client socket")
        sock.close()
    
'''reads multiple tags from a tag server. tag names must be provided as a list even
if there is only a single tag being read'''
def readTags(names, plc = "user"):
    outdict = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tserver_addr = ('localhost',12897)
    print("tag client attempting to connect to  and read from {host}:{port}".format(host = tserver_addr[0], port = tserver_addr[1]))
    
    try:
        sock.connect(tserver_addr)
        
        message = "read {plc}".format(plc = plc)
        for index,name in enumerate(names):
            message = message + " " + name
        message = message + "\n"
        sock.sendall(message)
        
        data = sock.recv(1024)
        print("tag client received: {info}".format(info = data))
        pairs = data.split(",")
        for pair in pairs:
            name,value = data.split(":")
            outdict[name] = value
        return outdict
        
            
    except Exception:
        print("tag client experiencing problem")
    finally:
        print("closing tag client socket")
        sock.close()
    
    
    
