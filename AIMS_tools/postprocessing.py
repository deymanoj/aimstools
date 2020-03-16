import ase.io, ase.cell

from AIMS_tools.structuretools import structure
from AIMS_tools.misc import *


class postprocess:
    """ A base class that retrieves information from finished calculations.

    Args:
        path (pathlib object): Directory of outputfile.

    Attributes:
        success (bool): If output file contained "Have a nice day".
        calc_type (set): Set of requested calculation types.
        active_SOC (bool): If spin-orbit coupling was included in the control.in file.
        active_GW (bool): If GW was included in the control.in file.
        spin (int): Spin channel.
        fermi_level (float): Fermi level energy value in eV.
        smallest_direct_gap (str): Smallest direct gap from outputfile.
        VBM (float): Valence band maximum energy in eV.
        CBM (float): Conduction band minimum energy in eV.        
        structure (structure): AIMS_tools.structuretools.structure object.
        color_dict (dict): Dictionary of atom labels and JMOL color tuples.        
     """

    def __init__(self, outputfile, get_SOC=True, spin=None):
        self.success = self.__check_output(outputfile)
        if spin in ["up", 1]:
            self.spin = 1
        elif spin in ["down", 2, "dn"]:
            self.spin = 2
        else:
            self.spin = None

        self.__read_geometry()
        self.__read_control()
        self.__read_output()
        self.color_dict = color_dict

    def __repr__(self):
        return str(self.outputfile)

    def __check_output(self, outputfile):
        if Path(outputfile).is_file():
            check = os.popen(
                "tail -n 10 {filepath}".format(filepath=Path(outputfile))
            ).read()
            if "Have a nice day." in check:
                self.outputfile = Path(outputfile)
                self.path = self.outputfile.parent
                logging.info("Found outputfile {}".format(self.outputfile))
                return True
            else:
                logging.error("Calculation did not converge!")
                return False

        elif Path(outputfile).is_dir():
            outfiles = Path(outputfile).glob("*.out")
            if len(list(outfiles)) == 0:
                logging.critical("Output file does not exist.")
            else:
                for i in outfiles:
                    check = os.popen("tail -n 10 {filepath}".format(filepath=i)).read()
                    if "Have a nice day." in check:
                        self.outputfile = i
                        self.path = self.outputfile.parent
                        logging.info("Found outputfile {}".format(self.outputfile))
                        return True
                else:
                    logging.error("Calculation did not converge!")
                    return False
        else:
            logging.critical("Could not find outputfile.")
            return False

    def __read_geometry(self):
        geometry = self.path.joinpath("geometry.in")
        self.structure = structure(geometry)

    def __read_control(self):
        control = self.path.joinpath("control.in")
        bandlines = []
        self.active_SOC = False
        self.active_GW = False
        self.calc_type = set()
        with open(control, "r") as file:
            for line in file.readlines():
                read = False if line.startswith("#") else True
                if read:
                    if "output band" in line:
                        bandlines.append(line.split())
                        self.calc_type.add("BS")
                    if "include_spin_orbit" in line:
                        self.active_SOC = True
                    if "k_grid" in line:
                        self.k_grid = (
                            line.split()[-3],
                            line.split()[-2],
                            line.split()[-1],
                        )
                    if "qpe_calc" in line and "gw" in line:
                        self.active_GW = True
                    if (
                        ("spin" in line)
                        and ("collinear" in line)
                        and (self.spin == None)
                    ):
                        self.spin = 1
                    if "output atom_proj_dos" in line:
                        self.calc_type.add("DOS")
        ## band structure specific information
        if "BS" in self.calc_type:
            self.ksections = []
            self.kvectors = {"G": np.array([0.0, 0.0, 0.0])}
            for entry in bandlines:
                self.ksections.append((entry[-2], entry[-1]))
                self.kvectors[entry[-1]] = np.array(
                    [entry[5], entry[6], entry[7]], dtype=float
                )
                self.kvectors[entry[-2]] = np.array(
                    [entry[2], entry[3], entry[4]], dtype=float
                )

    def __read_output(self):
        # Retrieve information such as Fermi level and band gap from output file.
        self.smallest_direct_gap = "Direct gap not determined. This usually happens if the fundamental gap is direct."
        with open(self.outputfile, "r") as file:
            for line in file.readlines():
                if "Chemical potential" in line:
                    if self.spin != None:
                        if "spin up" in line:
                            up_fermi_level = float(line.split()[-2])
                        elif "spin dn" in line:
                            down_fermi_level = float(line.split()[-2])
                            self.fermi_level = max([up_fermi_level, down_fermi_level])
                if "Chemical potential (Fermi level)" in line:
                    fermi_level = line.replace("eV", "")
                    self.fermi_level = float(fermi_level.split()[-1])
                if "Smallest direct gap :" in line:
                    self.smallest_direct_gap = line
                if "Number of k-points" in line:
                    self.k_points = int(line.split()[-1])
                if "Highest occupied state (VBM) at" in line:
                    self.VBM = float(line.split()[5])
                if "Lowest unoccupied state (CBM) at" in line:
                    self.CBM = float(line.split()[5])
                if "Chemical potential is" in line:
                    self.fermi_level = float(line.split()[-2])


class hirshfeld(postprocess):
    """ A simple class to evaluate Hirshfeld charge analysis from AIMS.

    Args:
        outputfile (str): Path to outputfile.

    Attributes:
        charges (dict): Dictionary of (index, species) tuples and hirshfeld charges. 
        tot_charges (dict): Dictionary of species and summed hirshfeld charges.
    
    """

    def __init__(self, outputfile, get_SOC=True, spin=None):
        super().__init__(outputfile, get_SOC=get_SOC, spin=spin)
        self.charges = self.read_charges()
        self.tot_charges = self.sum_charges()

    def read_charges(self):
        with open(self.outputfile, "r") as file:
            ats = []
            charges = []
            read = False
            for line in file.readlines():
                if "Performing Hirshfeld analysis" in line:
                    read = True
                    i = 0
                if read:
                    if "Atom" in line:
                        ats.append(
                            (int(line.split()[-2].strip(":")) - 1, line.split()[-1])
                        )
                    if "Hirshfeld charge        :" in line:
                        charges.append(float(line.split()[-1]))
                        i += 1
                        if i == self.structure.atoms.get_global_number_of_atoms():
                            read = False
        charges = dict(zip(ats, charges))
        return charges

    def sum_charges(self, fragment_filter=[]):
        """ Sums charges of given indices of atoms for the same species.
        
        Args:
            filter (list): List of atom indices. If None, all atoms of same species will be summed up.
        
        Example:
            >>> from AIMS_tools.structuretools import structure
            >>> from AIMS_tools.postprocessing import hirshfeld
            >>> hs = hirshfeld.hirshfeld("outputfile")
            >>> frag1 = hs.structure.fragments[0][0]
            >>> hs.sum_charges(frag1)
            
        """
        indices = {i: j for i, j in self.charges.keys()}

        fragment_filter = (
            [i[0] for i in self.charges.keys()]
            if fragment_filter == []
            else fragment_filter
        )

        sum_charges = {}
        for atom in fragment_filter:
            species = indices[atom]
            if species not in sum_charges.keys():
                sum_charges[species] = self.charges[(atom, species)]
            else:
                sum_charges[species] += self.charges[(atom, species)]
        return sum_charges

