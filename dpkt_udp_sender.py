#! /usr/bin/python
# -*- coding: utf-8 -*-
#
# A simple UDP packet sender This can send a very large UDP packet to demonstrate fragmentation
# of a UDP packet, so we can test packet reassembly
import socket
import getopt
import sys
import dpkt
import struct


def help() :
    print sys.argv[0] + """ -6h -s size -d destination_IP_addr
-6        Use IPv6 (default is IP4) (must come before -d if ipV6)
-d IP     destination IP address (either IPv4 or IPv6) (required)
-s size   size of the UDP packet (0 < size < 65536, upper limit is not enforced, default is 4096
-p port   destination port (default is 50005, 0< port < 65536)
-h        help
"""
    sys.exit(2)


def parse_args ( ) :
    """Parse the command line arguments.  The arguments are:
-6        Use IPv6 (default is IP4) (must come before -d if ipV6)
-d IP     destination IP address (either IPv4 or IPv6) (required)
-s size   size of the UDP packet (0 < size < 65536, upper limit is not enforced, default is 4096
-p port   destination port (default is 50005, 0< port < 65536)
-h        help
"""
    try :
        optlist, args = getopt.getopt ( sys.argv[1:], "6d:s:h")
        ipv6 = 0
        destination_ip = ""
        destination_port = 50005
        message_size = 4096
        for opt in optlist :
            if opt[0] == "-6" : ipv6 = 1
            elif opt[0] == "-d" :
               destination_ip = opt[1]
            elif opt[0] == "-s" :
                message_size = int( opt[1] )
            elif opt[0] == "-p" :
                destination_port = int( opt[1] )
                if not ( 0 < destination_port < 65536 ) :
                    raise ValueError 
            elif opt[0] == "-h" :
                help()
        if destination_ip == ""  :
            print "The -d DESTINATION_IP switch is required"
            raise ValueError
    except ( getopt.GetoptError, ValueError ) :
        help()
    return (destination_ip, destination_port, message_size, ipv6)


def create_udp_packet (destination_ip, destination_port, message_size, ipv6) :
    udp = dpkt.udp.UDP()
    udp.sport = 50004               # UDP source port, doesn't really matter
    udp.dport = destination_port
    udp.ulen = message_size
    message = message_size * "*"
    udp.data = message
# Need to calculate a UDP checksum
    return udp.pack()

def createRawIPSocket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
    return sock

if __name__ == "__main__" :
    (destination_ip, destination_port, message_size, ipv6) = parse_args( )
    sock = createRawIPSocket()
    udp_packet = create_udp_packet (destination_ip, destination_port, message_size, ipv6)
# The udp packet also has the destination IP and port, but sendto needs this information as well.
# The udp packet needs that information in order to calculate a checksum
    sock.sendto(udp_packet, (destination_ip, destination_port ) )



