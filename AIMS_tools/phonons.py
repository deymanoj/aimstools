import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.gridspec as gridspec

import ase.io, ase.cell

from AIMS_tools.misc import *


class phonon_bandstructure:
    """ Phonon band structure object.

    Processes files generated by phonopy-FHI-AIMS for plotting.
    
    Example:    
        >>> from AIMS_tools import phonons
        >>> import matplotlib.pyplot as plt
        >>> import numpy as np
        >>> phbs = phonons.phonon_bandstructure("directory")
        >>> phbs.plot()
        >>> plt.show()
        >>> plt.savefig("Name.png", dpi=300, transparent=False, bbox_inches="tight", facecolor="white")

    Args:    
        directory (str): Path to directory with phonopy results.
    
    Attributes:
        ksections (dict): Dictionary of (x1, x2) : (label_1, label_2) pairs, corresponding to real q distances.
        spectrum (ndarray): Array of q distances and frequencies.
     """

    def __init__(self, directory):
        self.path = Path(directory)
        if self.path.is_file():
            self.path = self.path.parents[0]
            files = [str(i.parts[-1]) for i in list(self.path.glob("*"))]
            assert ("geometry.in" in files) and (
                "control.in" in files
            ), "No AIMS calculation found."
        if self.path.is_dir():
            assert (
                len(list(self.path.glob("phonopy-FHI-aims-band_structure.dat"))) != 0
            ), "No phonopy results found."
        phononfile = self.path.joinpath("phonopy-FHI-aims-band_structure.dat")
        self.ksections, self.spectrum = self.__read_phononfile(phononfile)

    def __read_phononfile(self, phononfile):
        with open(phononfile, "r") as file:
            content = file.readlines()
        info = [line.strip() for line in content if "#" in line]
        data = [line.strip().split() for line in content if "#" not in line]

        ksections = {}
        for i in range(len(info)):
            if "Start point" in info[i]:
                line = info[i]
                start = line.split()[6]
                sval = float(line.split()[-1])
                line = info[i + 1]
                end = line.split()[6]
                endval = float(line.split()[-1])
                ksections[(sval, endval)] = (start, end)

        from itertools import groupby

        data = [list(group) for k, group in groupby(data, lambda x: x == []) if not k]
        data = np.array(data, dtype=float)  # (nksections, nsteps, nbands)
        data = data.reshape((data.shape[0] * data.shape[1], data.shape[2]))
        return ksections, data

    def plot(self, title="", fig=None, axes=None, color=("crimson", "k"), kwargs={}):
        """Plots a phonon band structure instance.
            
            Args:
                title (str): Title of the plot.
                fig (matplotlib figure): Figure to draw the plot on.
                axes (matplotlib axes): Axes to draw the plot on.
                color (tuple): Color of accustic and optical branches.
                **kwargs (dict): Passed to matplotlib plotting function.

            Returns:
                axes: matplotlib axes object"""
        if fig == None:
            fig = plt.figure(figsize=((self.spectrum[-1][0]) / 2, 3))
        if axes == None:
            axes = plt.gca()
        x = self.spectrum[:, 0]
        y = self.spectrum[:, 1:]
        clist = [color[0]] * 3
        clist += [color[1] for i in range(y.shape[1] - 3)]
        for j in range(len(clist)):
            axes.plot(x, y[:, j], color=clist[j], **kwargs)
        label_coords = [list(self.ksections.keys())[0][0]]
        label_coords += [j[1] for j in self.ksections.keys()]
        labels = [list(self.ksections.values())[0][0]]
        labels += [j[1] for j in self.ksections.values()]
        axes.set_xticks(label_coords)
        for i in range(len(labels)):
            if labels[i] == "G":
                labels[i] = "$\Gamma$"
        axes.set_xticklabels(labels)
        axes.set_ylabel(r"Frequency $\nu$ [cm$^{-1}$]")
        axes.set_xlim(min(label_coords), max(label_coords))
        ylocs = ticker.MultipleLocator(
            base=50
        )  # this locator puts ticks at regular intervals
        axes.yaxis.set_major_locator(ylocs)
        axes.set_xlabel("")
        axes.axhline(y=0, color="k", alpha=0.5, linestyle="--")
        axes.grid(which="major", axis="x", linestyle=":")
        axes.set_title(str(title), loc="center")
        return axes


class phonon_dos:
    """ Phonon density of states object.

    Processes files generated by phonopy-FHI-AIMS for plotting.

    """

    def __init__(self, directory):
        self.path = Path(directory)
        if self.path.is_file():
            self.path = self.path.parents[0]
            files = [str(i.parts[-1]) for i in list(self.path.glob("*"))]
            assert ("geometry.in" in files) and (
                "control.in" in files
            ), "No AIMS calculation found."
        if self.path.is_dir():
            assert (
                len(list(self.path.glob("phonopy-FHI-aims-dos.dat"))) != 0
            ), "No phonopy results found."
        dosfile = self.path.joinpath("phonopy-FHI-aims-dos.dat")
        self.spectrum = self.__read_dosfile(dosfile)

    def __read_dosfile(self, dosfile):
        with open(dosfile, "r") as file:
            content = [
                line.strip().split() for line in file.readlines() if "#" not in line
            ]
        data = np.array(content, dtype=float)
        return data

    def plot(self, fig=None, axes=None, color="k"):
        if fig == None:
            fig = plt.figure(figsize=(2, 4))
        if axes == None:
            axes = plt.gca()
        x = self.spectrum[:, 1]
        y = self.spectrum[:, 0]
        axes.plot(x, y, color=color)
        axes.set_xlim((0, np.max(x * 1.05)))
        axes.set_xticks([])
        axes.set_xlabel("DOS")
        return axes


def plot_bs_dos(directory, title=""):
    """ Combines a phonon band structure plot and phonon densities of states plot.
    
    Args:
        BSpath (str): Path to band structure calculation output file.
        DOSpath (str): Path to density of states calculation output file.
        title (str, optional): Ttile of the plot
        fix_energy_limits (list, optional): List of lower and upper energy limits to show. Defaults to [].
    
    Returns:
        figure: matplotlib figure object
    """
    fig = plt.figure(constrained_layout=True, figsize=(4, 4))
    spec = gridspec.GridSpec(ncols=2, nrows=1, figure=fig, width_ratios=[3, 1])
    ax1 = fig.add_subplot(spec[0])
    ax2 = fig.add_subplot(spec[1])

    ## Handle bandstructures
    plt.sca(ax1)
    bs = phonon_bandstructure(directory)
    ax1 = bs.plot(fig=fig, axes=ax1)
    ymin, ymax = ax1.get_ylim()

    ## Handle DOS
    plt.sca(ax2)
    dos = phonon_dos(directory)
    ax2 = dos.plot(fig=fig, axes=ax2)
    ax2.set_ylabel("")
    ax2.set_yticks([])
    ax2.set_ylim(ymin, ymax)

    fig.suptitle(title)
    return fig
