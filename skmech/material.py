"""Module that contains material properties in a class"""


class Material(object):
    """Instanciate a material object

    Parameters
    ----------
    case : str {'stress', 'strain'}
        Plane stress or plane strain cases

    Attributes
    ----------
    mat_dic keywords : dict
        dictionary with surface label and material paramenter value.

        Example:

            Material(E={9: 1000, 10: 2000},
                     nu={9: 0.3, 10: .2})

        then, the keyword `E` is the attribute self.E with value
        {9: 1000} in which 9 is the surface label and 1000 is the
        E value at that surface, the second item in the dic is
        other surface.

        For level sets, the material is defined using regions -1,
        for reinforcement, and 1 for matrix.

    Note
    ----
    If case is strain, then we use the standard transformations
    in the material parameters, E and nu, in order to avoid
    changing the construction of the constitutive matrix.

    """
    def __init__(self, case='stress', **mat_dic):
        try:
            self.E = mat_dic['E']
        except KeyError:
            raise Exception('Missing E')
        try:
            self.nu = mat_dic['nu']
        except KeyError:
            raise Exception('Missing nu')

        # Add additional material parametrs if they exist in mat_dic
        # hardening modulus
        try:
            self.H = mat_dic['H']
        except KeyError:
            pass
        # yield stress
        try:
            self.sig_y0 = mat_dic['sig_y0']
        except KeyError:
            pass

        self.case = case


if __name__ is '__main__':
    # surface 0 with E=10
    # surface 1 with E=20
    mat = Material(E={0: 10, 1: 20, 2:30}, nu={0: .1})
    # print(mat.E) # {0: 10, 1: 20, 2: 30}
    # mat_strain = Material(E={0: 10, 1: 20, 2:30},
    #                       nu={0: .3, 1: .2, 2: .33},
    #                       case='strain')
    # # print(mat_strain.E){0: 10.989, 1: 20.83, 2: 33.666}
    # mat_lvlset = Material(E=[{-1: 1000, 1: 2000},
    #                          {-1: 1000, 1: 5000}],
    #                       nu=[{-1: .3, 1: .35},
    #                           {-1: .3, 1: .4}])
    # # print(mat_lvlset.E) [{-1: 1000, 1: 2000}, {-1: 1000, 1: 5000}]
    mat_lvlset2 = Material(E={-1: 1000, 1: 2000},
                           nu={-1: .3, 1: .35}, case='strain')
    print(mat_lvlset2.nu)
