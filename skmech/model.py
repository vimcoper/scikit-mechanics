"""Module for building the structure model

This module contains the class that creates the
structure model.

"""
import numpy as np
from .xfem.xfem import Xfem


class Model(object):
    """Build the model object

    Parameters
    ----------

    Attributes
    ----------

    Note
    ----
    The objects mesh and material are aggregated into model object.
    The xfem object is included by instanciated its class if a zerolevel set
    is passed (composition).

    """
    def __init__(self, mesh, material=None, traction=None,
                 displacement_bc=None, body_forces=None, zerolevelset=None,
                 imposed_displ=None,
                 num_quad_points=2, thickness=1., etypes=[3]):
        self.mesh = mesh
        self.material = material
        self.traction = traction
        self.body_forces = body_forces
        self.displacement_bc = displacement_bc
        self.imposed_displ = imposed_displ
        self.thickness = thickness

        # solution after calling the solver
        self.dof_displacement = 0

        self.etypes = etypes
        self.elements = self._get_elements(mesh.elements)
        self.nodes = mesh.nodes

        self.num_ele = len(self.mesh.elements)
        self.num_quad_points = self._get_number_quad_points(num_quad_points)
        self.num_nodes = len(self.mesh.nodes)
        self.num_dof_node = self._get_number_dof()
        self.num_dof = self.num_nodes * self.num_dof_node

        # TODO: maybe a Node class will be useful
        # too many node related attributes:
        # nodes.coord, nodes.num_dof, nodes.dof, nodes.num_dof_pernode,
        self.nodes_dof = self._generate_dof()

        # connectivity matrices for partinioning the system of equations
        self.Lf, self.Lr = self.get_connectivity_matrices()

        if zerolevelset is None:
            self.xfem = None
        else:
            self.xfem = Xfem(self.nodes, self.elements,
                             zerolevelset, material)
            self.num_dof = self.xfem.num_dof            # update num dof


    def get_connectivity_matrices(self):
        """Compute connectivity matrix for free and restrained dofs"""
        Lf, Lr = [], []
        if self.displacement_bc is not None:
            for d_loc, d_value in self.displacement_bc.items():
                physical_element = self.get_physical_element(d_loc)
                for eid, [etype, *edata] in physical_element.items():
                    # physical points
                    if etype == 15:
                        node = edata[-1]  # last entry
                        dof = np.array(self.nodes_dof[node]) - 1
                        if d_value[0] is not None:
                            lr = np.zeros(self.num_dof)
                            lr[dof[0]] = 1
                            Lr.append(lr)
                        if d_value[1] is not None:
                            lr = np.zeros(self.num_dof)
                            lr[dof[1]] = 1
                            Lr.append(lr)
                    # physical lines
                    if etype == 1:
                        node_1, node_2 = edata[-2], edata[-1]
                        dof_n1 = np.array(self.nodes_dof[node_1]) - 1
                        dof_n2 = np.array(self.nodes_dof[node_2]) - 1
                        if d_value[0] is not None:
                            lr_n1 = np.zeros(self.num_dof)
                            lr_n1[dof_n1[0]] = 1
                            Lr.append(lr_n1)
                            lr_n2 = np.zeros(self.num_dof)
                            lr_n2[dof_n2[0]] = 1
                            Lr.append(lr_n2)
                        if d_value[1] is not None:
                            lr_n1 = np.zeros(self.num_dof)
                            lr_n1[dof_n1[1]] = 1
                            Lr.append(lr_n1)
                            lr_n2 = np.zeros(self.num_dof)
                            lr_n2[dof_n2[1]] = 1
                            Lr.append(lr_n2)

        return np.array(Lf), np.array(Lr)

    def set_dof_displacement(self, displacement):
        """Set the dof displacemnt into model attribute"""
        self.dof_displacement = displacement

    def get_physical_element(self, physical_element):
        """Get physical line element

        Parameters
        ----------
        physical_element : int
            tag of the physical element where the traction is assigned
        elements : dict
            dictionary with all mesh elements from gmsh

        Returns
        -------
        dict
            dictionary with element data that are in the physical element

        """
        return {key: value
                for key, value in self.mesh.elements.items()
                if value[2] == physical_element}

    def _generate_dof(self):
        """Generate nodal degree of freedom

        This is done based on nodal tag, element type and number of dof
        per node.
        Starts at 1.

        Returns
        -------
        dict
            dictionary with node tag and respective degree's of freedom
            associated with this node

        """
        dof = {}
        for nid, _ in self.mesh.nodes.items():
            dof[nid] = [nid * self.num_dof_node - 1 + i
                        for i in range(self.num_dof_node)]
        return dof

    def _get_elements(self, elements):
        """Select only declared elements from msh file

        Parameters
        ----------
        elements : dict
            dictionary with all elements produced by gmsh

        Returns
        -------
        dict
            dictionary with element type and element data if element
            type is in declared etypes list

        """
        return {key: value
                for key, value in elements.items()
                if value[0] in self.etypes}

    def _get_number_dof(self):
        """Compute number os dof per node"""
        if 3 in self.etypes:
            num_dof_node = 2
        elif 1 in self.etypes:
            # spatial frame
            num_dof_node = 6
        elif 5 in self.etypes:
            # hexaedro
            num_dof_node = 3
        else:
            raise Exception('Element not implemented!')
        return num_dof_node

    def _get_number_quad_points(self, num_quad_points):
        """Compute number of quad points for each element

        Parameters
        ----------
        num_quad_points : int

        Returns
        -------
        dict
            dictionary with element id and number of quad points

        """
        return {key: value
                for key, value in
                zip(self.mesh.elements.keys(),
                    [num_quad_points] * self.num_ele)}


if __name__ == '__main__':
    pass
