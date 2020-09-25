#!/usr/bin/python3
import requests
import os.path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

def download_file(filename, url):
    """
    Download an URL to a file
    """
    with open(str(filename), 'wb') as fout:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        # Write response data to file
        for block in response.iter_content(4096):
            fout.write(block)
def download_if_not_exists(url,filename):
    """
    Download a URL to a file if the file
    does not exist already.
    Returns
    -------
    True if the file was downloaded,
    False if it already existed
    """
    if not os.path.exists(str(filename)):
        download_file(filename, url)
        return True
    return False

def extract (zip_file_path,destination_path):
    # Create a ZipFile Object and load sample.zip in it
    with ZipFile(zip_file_path, 'r') as zipObj:
        # Extract all the contents of zip file in different directory
        zipObj.extractall(destination_path)


def get_file_names_in_a_directory(dir):
    """
    Get all files in a directory dir
    """
    import os
    files = sorted([f for f in os.listdir(dir) if os.path.isfile(os.path.join(dir, f))])
    return files


def print_all_topos(extracted_dir):
    """
    Print all available topologies
    """
    for file_name in get_file_names_in_a_directory(extracted_dir):      
        if file_name.endswith(".graphml"):
            print(file_name.replace(".graphml",""))

class TopologyZooXML:
    """
    TopologyZooXML is a class for using XML files and Get topology matrix
    """
    def __init__(self,path):
        self.topology_zoo_xml_path = path
        self.root = ET.parse(path).getroot()
        self.switches = self.get_switches()
        self.edge_counter = self.get_edge_counter()
        self.edge_switches = self.get_edge_swithes()
        
    def get_switches (self):
        """
        Reads xml file and create list of all switches
        """
        switches = []
        for item in self.root.getchildren():
            for i in item.getchildren():
                if 'id' in i.keys():
                    switches.append((convert_id_to_dpid(int(i.attrib['id'])+1),int(i.attrib['id'])))
        return switches
    
   
    def get_edge_counter(self):
        """
        Reads xml file and create a dictionary of switch and count of it's connected links
        """
        edge_counter = {}  #{00:00:00:00:00:00:00:01:2,00:00:00:00:00:00:00:02:1}
       
        for sw1 in self.switches:
            edge_counter[sw1] = 0
        
        for item in self.root.getchildren():
            for i in item.getchildren():
                if 'source' in i.keys() and 'target' in  i.keys():
                    src_sw_dpid = convert_id_to_dpid(int(i.attrib['source'])+1)
                    edge_counter[(src_sw_dpid,int(i.attrib['source']))]=edge_counter[(src_sw_dpid,int(i.attrib['source']))]+1

        return edge_counter

    def get_edge_swithes(self):
        """
        Gets list of all edge switches
        """
        edge_switches = []
        for (sw,sw_id),edge_count in self.edge_counter.items():
            if edge_count is  1 or 2:
                edge_switches.append((sw,sw_id))
        return edge_switches

    def get_topology(self,number_of_hosts_to_be_added = 0 , random_hosts = False):
        """
        Gets topology in the following structrue:
        {first_switch_dpid or host_mac,second_switch_dpid,"h or s"}
        """
        final_topo = {}
        links_dup_check = {}

        for item in self.root.getchildren():
            for i in item.getchildren():
                if 'source' in i.keys() and 'target' in  i.keys():
                    src_sw_dpid = convert_id_to_dpid(int(i.attrib['source'])+1)
                    dst_sw_dpid = convert_id_to_dpid(int(i.attrib['target'])+1)

                    if (src_sw_dpid,dst_sw_dpid) not in links_dup_check and (dst_sw_dpid,src_sw_dpid) not in links_dup_check:
                        final_topo[((src_sw_dpid,int(i.attrib['source'])),(dst_sw_dpid,int(i.attrib['target'])),'s')] = 1
                        links_dup_check[(src_sw_dpid,dst_sw_dpid)] = True

        for sw in self.edge_switches:
            host_mac = sw[0][6:]
            final_topo[((host_mac,sw[1]),sw,'h')] = 1
        return final_topo

def convert_to_colon_separated (a):
    #a = "0000000000000001"
    for j in range(0, int(len(a) / 2)):
        if j == 0:
            continue
        a = a[0:2 * j + j - 1] + ":" + a[2 * j + j - 1:]
    # a = "00:00:00:00:00:00:00:01"
    return a

def convert_id_to_dpid (id):
    """
    param id: input switch id e.g. 1
    return : output dpid e.g. 00:00:00:00:00:00:00:01
    """
    return convert_to_colon_separated (format(id,'00000000000016x'))

def convert_id_to_mac (id):
    """
    param id: input switch id e.g. 1
    return : output dpid e.g. 00:00:00:00:00:00:00:01
    """
    return convert_to_colon_separated (format(id,'00000000000012x'))


class Mininet:
    def __init__(self,topology_graph,controller_ip,controller_port,controller_type):
        self.topology_graph = topology_graph
        self.controller_ip = controller_ip
        self.controller_port = controller_port
        self.controller_type = controller_type
        self.run_topo()

    def run_topo(self):
        from mininet.net import Mininet
        from mininet.node import Controller, RemoteController, OVSController
        from mininet.node import CPULimitedHost, Host, Node
        from mininet.node import OVSKernelSwitch, UserSwitch
        from mininet.node import IVSSwitch
        from mininet.cli import CLI
        from mininet.log import setLogLevel, info
        from mininet.link import TCLink, Intf
        from subprocess import call
        import ipaddress

        def myNetwork():
            net = Mininet( topo=None,
                        build=False,
                        ipBase='10.0.0.0/8')

            info( '*** Adding controller\n' )
            controller = None
            c0 = None
            
            if self.controller_type == "controller":
                controller = Controller
                self.controller_port = 6633
                c0=net.addController(name='c0',
                    controller=controller,
                    protocol='tcp',
                    port=self.controller_port)
            elif self.controller_type =="remote":
                controller = RemoteController
                c0=net.addController(name='c0',
                    controller=controller,
                    protocol='tcp',
                    ip=self.controller_ip,
                    port=self.controller_port)
            elif self.controller_type == "ovscontroller":
                controller = OVSController
                self.controller_port = 6633
                c0=net.addController(name='c0',
                    controller=controller,
                    protocol='tcp',
                    port=self.controller_port)
            else:
                c0=net.addController(name='c0',
                                controller=controller,
                                protocol='tcp',
                                ip=self.controller_ip,
                                port=self.controller_port)

            info( '*** Add switches\n')
            switches = {}
            added_switches={}
            for (first,second,node_type) in self.topology_graph:
                if node_type == "s":
                    if first[1] not in added_switches:
                        switches[first[1]] = net.addSwitch('s'+str(first[1]+1), cls=OVSKernelSwitch)
                        added_switches[first[1]] = True
                    if second[1] not in added_switches:
                        switches[second[1]] = net.addSwitch('s'+str(second[1]+1), 
                        cls=OVSKernelSwitch)
                        added_switches[second[1]] = True
                    

            info( '*** Add hosts\n')
            hosts= []
            
            first_ip = '10.0.0.0'
            for (first,second,node_type) in sorted(self.topology_graph):
                if node_type == "h":
                    #hosts.append(net.addHost('h'+str(i), cls=Host, defaultRoute=None))
                    if sys.version_info >= (3, 0):
                        hosts.append(net.addHost('h'+str(first[1]+1), cls=Host, ip=str(ipaddress.IPv4Address(int(ipaddress.IPv4Address(first_ip))+first[1]+1)), defaultRoute=None))
                    else:
                        hosts.append(net.addHost('h'+str(first[1]+1), cls=Host, defaultRoute=None))
                    

            info( '*** Add links\n')
            for (first,second,node_type) in self.topology_graph:
                try:
                    if node_type=="s":
                        net.addLink(switches[first[1]],switches[second[1]])
                    elif node_type=="h":
                        net.addLink(hosts[first[1]],switches[second[1]])
                except KeyError as e:
                    print("switch or host is unavailable: {}".format(e))


            info( '*** Starting network\n')
            net.build()
            info( '*** Starting controllers\n')
            for controller in net.controllers:
                controller.start()

            info( '*** Starting switches\n')
            for _,sw in switches.items():
                sw.start([c0])

            info( '*** Post configure switches and hosts\n')

            CLI(net)
            net.stop()

        setLogLevel( 'info' )
        myNetwork()


if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description='This script is a fast way to run topology\'s that are available in topologyzoo.com on mininet!')

    parser.add_argument('--availtopo', dest='avail_topo', help="prints list of all available topologies and exit.",required=False,action="store_true")

    parser.add_argument('--toponame', dest='topo_name', help="Topology name e.g. Abilene",required=False,type=str)
    parser.add_argument('--cport', dest='controller_port', help="Controller port in mininet, default value is 6653.",required=False,type=int,default=6653)
    parser.add_argument('--cip', dest='controller_ip', help="Controller ip in mininet, default value is 127.0.0.1.",required=False,type=str,default="127.0.0.1")

    parser.add_argument('--controller', dest='controller_type', help="Default controller is mininet controller, other options: remote,ovscontroller",required=False,type=str,default="controller")

    args = parser.parse_args()


    import tempfile
    tmp_dir = tempfile.gettempdir()

    archive_path = os.path.join(tmp_dir,"archive.zip")
    download_if_not_exists("http://www.topology-zoo.org/files/archive.zip",archive_path)
    extract (archive_path,os.path.join(tmp_dir,"topologyzoo"))

    if args.avail_topo:
        print_all_topos(os.path.join(tmp_dir,"topologyzoo"))
        exit(0)
    import sys
    if  args.topo_name==None:
        print ("you must specify at least one of the switches, use \"{} -h\" for help.".format(sys.argv[0]))
        exit(1)
        

    tzoo2= TopologyZooXML(os.path.join(tmp_dir,"topologyzoo",args.topo_name+".graphml"))
    m= Mininet(tzoo2.get_topology(),args.controller_ip,args.controller_port,args.controller_type)   
