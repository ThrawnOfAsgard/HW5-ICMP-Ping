import socket
import os
import sys
import struct
import time
import select

ICMP_ECHO_REQUEST = 8

def checksum(string):
    countTo = (len(string) // 2) * 2
    csum = 0
    count = 0

    while count < countTo:
        thisVal = string[count + 1] * 256 + string[count]
        csum = csum + thisVal
        csum = csum & 0xffffffff
        count = count + 2

    if countTo < len(string):
        csum = csum + string[-1]
        csum = csum & 0xffffffff

    csum = (csum >> 16) + (csum & 0xffff)
    csum = csum + (csum >> 16)
    answer = ~csum
    answer = answer & 0xffff
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer

def receiveOnePing(mySocket, ID, timeout, destAddr):
    timeLeft = timeout
    while True:
        startedSelect = time.time()
        whatReady = select.select([mySocket], [], [], timeLeft)
        howLongInSelect = time.time() - startedSelect

        if whatReady[0] == []: # Timeout
            return "Request timed out.", None #return error message and None for time

        timeReceived = time.time()
        recPacket, addr = mySocket.recvfrom(1024)

        #Fill in start
        #Fetch the ICMP header from the IP packet
        ipHeaderLength = (recPacket[0] & 0x0F) * 4
        icmpHeader = recPacket[ipHeaderLength:ipHeaderLength + 8]
        type, code, checksum, packetID, sequence = struct.unpack("bbHHh", icmpHeader)

        #to check for errors
        if type != 0:
            if code == 0:
                return "0: Destination Network Unreachable", None
            if code == 1:
                return "1: Destination Host Unreachable", None
            if code == 3:
                return "3: Destination Port Unreachable", None
            
            if type == 11:
                return "Time Exceeded", None
            return f"ICMP Error: Type {type}, Code {code}"

        if packetID == ID:
            timeSent = struct.unpack("d", recPacket[ipHeaderLength + 8:ipHeaderLength + 16])[0]
            return None, timeReceived - timeSent #return None for error message and time
        #Fill in end

        timeLeft = timeLeft - howLongInSelect
        if timeLeft <= 0:
            return "Request timed out.", None #return error message and None for time

def sendOnePing(mySocket, destAddr, ID):
    # Header is type (8), code (8), checksum (16), id (16), sequence (16)
    myChecksum = 0
    # Make a dummy header with a 0 checksum
    # struct -- Interpret strings as packed binary data
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, 0, ID, 1)
    data = struct.pack("d", time.time())
    # Calculate the checksum on the data and the dummy header.
    myChecksum = checksum(header + data)

    # Get the right checksum, and put in the header
    if sys.platform == 'darwin':
        # Convert 16-bit integers from host to network byte order
        myChecksum = socket.htons(myChecksum) & 0xffff
    else:
        myChecksum = socket.htons(myChecksum)

    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    packet = header + data
    mySocket.sendto(packet, (destAddr, 0)) # AF_INET address must be tuple, not str
    # Both LISTS and TUPLES consist of a number of objects
    # which can be referenced by their position number within the object.

def doOnePing(destAddr, timeout):
    icmp = socket.getprotobyname("icmp")
    # SOCK_RAW is a powerful socket type. For more details: http://sock-raw.org/papers/sock_raw

    mySocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)

    myID = os.getpid() & 0xFFFF
    sendOnePing(mySocket, destAddr, myID)
    delay = receiveOnePing(mySocket, myID, timeout, destAddr)
    mySocket.close()
    return delay

def ping(host, timeout=1, count=10):
    #added count of 10 to get percentage for packet loss rate
    #timeout=1 means: If one second goes by without a reply from the server,
    #the client assumes that either the client’s ping or the server’s pong is lost
    dest = socket.gethostbyname(host)
    print("Pinging " + dest + " using Python:\n")
    #Send ping requests to a server separated by approximately one second
    # while 1 :
    #   delay = doOnePing(dest, timeout)
    #   print(delay)
    #   time.sleep(1) # one second

    #Modified to send count (10) ping requests to a server separated by approximately one second
    rtts = []
    sentPackets = 0
    receivedPackets = 0

    for i in range(count):
        sentPackets = sentPackets + 1

        # delay = doOnePing(dest, timeout)
        #modified to check for error and time
        error, delay = doOnePing(dest, timeout)

        if delay is not None:
            receivedPackets = receivedPackets + 1
            rtts.append(delay)
            print(delay)
            print(f"Reply from {dest}: time = {round(delay * 1000, 2)}ms\n")
        elif error:
            print(f"Error from {dest}: {error}")
        else:
            print("\nRequest timed out.")
        time.sleep(1) # one second

    lossRate = ((sentPackets - receivedPackets) / sentPackets) * 100
    print(f"{sentPackets} packets sent, {receivedPackets} packets received, so loss rate of {lossRate: .2f}%")

    if rtts:
        rttMin = round(min(rtts) * 1000, 2)
        rttMax = round(max(rtts) * 1000, 2)
        rttAvg = round(sum(rtts) / len(rtts) * 1000, 2)
        print(f"RTT min is {rttMin}ms, max is {rttMax}ms, and average is {rttAvg}ms\n")
    else:
        print("No RTTs to report.")


ping("127.0.0.1")
