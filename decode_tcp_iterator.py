#!/usr/bin/env python
#
# This module implements a TCP receiver.  Refer to RFC 793 http://www.rfc-editor.org/rfc/rfc793.txt for details.

import dpkt
import sys
import socket
import pcap

def connection_id_to_str (cid, v=4) :
    """This converts the connection ID cid which is a tuple of (source_ip_address, source_tcp_port, destination_ip_address,
destination_tcp_port) to a string.  v is either 4 for IPv4 or 6 for IPv6"""
    if v == 4 :
        src_ip_addr_str = socket.inet_ntoa(cid[0])
        dst_ip_addr_str = socket.inet_ntoa(cid[2])
        return src_ip_addr_str + ":" + str(cid[1])+"=>"+dst_ip_addr_str + ":" + str(cid[3])
    elif v == 6 :
        src_ip_addr_str = socket.inet_ntop(AF_INET6, cid[0])
        dst_ip_addr_str = socket.inet_ntop(AF_INET6, cid[2])
        return src_ip_addr_str + "." + str(cid[1])+"=>"+dst_ip_addr_str + "." + str(cid[3])
    else :
        raise ValueError('Argument to connection_id_to_str must be 4 or 6, is %d' % v)

class Connection_object :
    """A connection object stores the state of the tcp connection"""
    def __init__ ( self, isn, seq, string  ) :
        self.isn = isn              # initial sequence number.  All sequence numbers are relative to this number.
        self.seq = seq                       # last sequence number seen.  I'm not sure I need to keep this.
        self.buffer = { seq: string }        # the keys are the relative sequence numbers, the values are the strings
        

def assemble_buffer( buffer_dictionary ) :
    """The buffer dictionary contains segment numbers, which are byte offsets into the stream, and the bytes that the offsets point to.  This
function assembles the buffer into order.  It should raise an exception if there is missing data - this is not implemented"""
    return_buffer = ""
    for segment in sorted( buffer_dictionary.keys() ) :
        read_end = len(return_buffer)
        if read_end+1 != segment :
            print "There is a segment missing between %d (already read) and %d (current segment beginning)" % ( read_end, segment )
        return_buffer = return_buffer + buffer_dictionary[segment]
    return return_buffer    

def decode_tcp(pcap):
    """This function decodes a packet capture file f and breaks it up into tcp connections"""
    print "counter\tsrc prt\tdst prt\tflags"
    packet_cntr = 0
    connection_table = {}   # the keys of the table are the connection ID strings: source IP,
                            # source port, destination IP, destination port.  The values are a tuple which is the
                            # sequence number and a string which is the assembled stream

    for ts, buf in pcap:
        packet_cntr += 1
        eth = dpkt.ethernet.Ethernet(buf)
# Also, this changes a little bit with IPv6.  To tell the difference between IPv4 and IPv6, you have to look
# at the ethertype field, which is given by http://www.iana.org/assignments/ethernet-numbers.  IPv4 is 0x800 or 2048
# and IPv6 is 0x86DD or 34525
# This is simplistic - IPv4 packets can be fragmented.  Also, this only works for IPv4.  IPv6 has a different Ethertype    
        if eth.type == dpkt.ethernet.ETH_TYPE_IP :
            ip = eth.data
            if ip.v != 4 :
                raise ValueError, "In packet %d, the ether type is IPv4 but the IP version number is %d not 4" % (
                    packet_cntr, ip.v )
           # Deal with fragmentation here
        elif eth.type == dpkt.ethernet.ETH_TYPE_IP6 :
            ip = eth.data
            if ip.v != 6 :
                raise ValueError, "In packet %d, the ether type is IPv6 but the IP version number is %d not 6" % (
                    packet_cntr, ip.v )
            # IPv6 packets don't fragment            
        else :
            print "packet %d is neither IPv4 nor IPv6" % packet_cntr
            continue    # Not going to deal with anything other than IP
        if ip.p == dpkt.ip.IP_PROTO_TCP :
            tcp = ip.data
            fin_flag = ( tcp.flags & 0x01 ) != 0
            syn_flag = ( tcp.flags & 0x02 ) != 0
            rst_flag = ( tcp.flags & 0x04 ) != 0
            psh_flag = ( tcp.flags & 0x08 ) != 0
            ack_flag = ( tcp.flags & 0x10 ) != 0
            urg_flag = ( tcp.flags & 0x20 ) != 0
            ece_flag = ( tcp.flags & 0x40 ) != 0
            cwr_flag = ( tcp.flags & 0x80 ) != 0
# The flags string is really for debugging
            flags = (
                ( "C" if cwr_flag else " " ) +
                ( "E" if ece_flag else " " ) +
                ( "U" if urg_flag else " " ) +
                ( "A" if ack_flag else " " ) +
                ( "P" if psh_flag else " " ) +
                ( "R" if rst_flag else " " ) +
                ( "S" if syn_flag else " " ) +
                ( "F" if fin_flag else " " ) )
        if syn_flag and not ack_flag :
# Each TCP connection is forming.  The new connection is stored as an object in a dictionary
# whose key is the tuple (source_ip_address, source_tcp_port, destination_ip_address, destination_tcp_port)
# The connection is stored in a dictionary.  The key is the connection_id, value of each key is an object with fields for the
# current connection state and the total of all the bytes that have been sent
# Note that there are two connections, one from the client to the server and one from the server to the client.  This becomes
# important when the connection is closed, because one side might FIN the connection well before the other side does.
            connection_id = (ip.src, tcp.sport, ip.dst, tcp.dport)
            print "Forming a new connection " + connection_id_to_str( connection_id, ip.v ) + " Initial Sequence Number (ISN) is %d" % tcp.seq
# Should decode the maximum segment size from the options list
            options_list = dpkt.tcp.parse_opts ( tcp.opts )
            connection_table[connection_id] = Connection_object ( isn = tcp.seq, seq = tcp.seq, string = "" )
        elif syn_flag and ack_flag :
            print "Server responding to a new connection " + connection_id_to_str( connection_id, ip.v )
            connection_table[connection_id]
    # This is where I am having a little confusion.  My instinct tells me that the connection from the client to the server and the
    # connection from the server back to the client should be connected somehow.  But they aren't, except for the SYN-ACK
    # packet.  Otherwise, the source IP, destination IP, source port and destination port are mirror images, but the streams
    # are separate.  The acknowlegement numbers are related, but we don't need to worry about acknowlegements
        elif not syn_flag and ack_flag :
            sequence_number = tcp.seq
            byte_offset = sequence_number - connection_table[connection_id].isn
            connection_table[connection_id].buffer[byte_offset] = tcp.data
            connection_table[connection_id].seq = sequence_number
# if the push flag is set, then return the string to the caller, along with identifying information so that the
# caller knows which connection is getting data returned.
            if psh_flag or urg_flag :
                connection_string = assemble_buffer( connection_table[connection_id].buffer )
                yield ( connection_id, connection_string )


def main(pc) :
    """This is the outer loop that prints strings that have been captured from the TCP streams, terminated by a packet that
has the PUSH flag set."""
    for connection_id, received_string in decode_tcp(pc) :
        print connection_id, received_string               
                        
                        

if __name__ == "__main__" :
    if len(sys.argv[1]) < 2 :
        decode_tcp_help()
# create an interator to return the next packet.  The source can be either an interface using the libpcap library or it can be a file in pcap
# format such as created by tcpdump.
    if sys.argv[1] == "eth0" :                  # wired ethernet interface
        pc = pcap.pcap("eth0", promisc=True )
    elif sys.argv[1] == "wlan0" :               # wireless interface
        pc = pcap.pcap("wlan0", promisc=True )
    else :
        pc = dpkt.pcap.Reader ( open(sys.argv[1] ) )    # file interface
    main(pc)

