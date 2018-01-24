"""Solves the incremental  problem"""
import numpy as np
import time
from ..dirichlet import dirichlet
from ..dirichlet import imposed_displacement
from ..neumann import neumann
from ..constructor import constructor
from ..plasticity.stateupdatemises import state_update_mises
from ..plasticity.tangentmises import consistent_tangent_mises
from ..postprocess.dof2node import dof2node
from ..meshplotlib.gmshio.gmshio import write_field


def solver(model, load_increment=None,
           imposed_displ=None,
           num_load_increments=10,
           max_num_iter=5, tol=1e-6,
           max_num_local_iter=100):
    """Performes the incremental solution of linearized virtual work equation

    Parameters
    ----------
    model : Model object
        object that contains the problem parameters: mesh, bc, etc

    Note
    ----
    Reference Box 4.2 Neto 2008

    """
    start = time.time()
    print('Starting incremental solver')

    # load increment
    # TODO: Question about the initial load increment DONE
    # does it starts at zero or at a very small number -> at 0
    # See feap examples manual
    if load_increment is None:
        load_increment = np.linspace(0, 1, num_load_increments)

    try:
        num_dof = model.num_dof
    except AttributeError:
        raise Exception('Model object does not have num_dof attribute')

    # numpy array to store solution for all dof
    displ = np.zeros((num_dof, len(load_increment)))

    # initial displacement for t_0 (n=0)
    u = np.zeros(num_dof)

    # initial elastic strain for each element gauss point
    # TODO: fixed for 4 gauss point for now
    # TODO: maybe put that in the element class
    # TODO: Question about initial elastic strain
    # initialize cummulatice plastic strain for each element gauss point
    # num_quad_points is a dictionary with {eid, num_quad_points}
    # num_quad_poins for each dimension, multiply by 2 for plane problems
    eps_e_n = {(eid, gp): np.zeros(3) for eid in model.elements.keys()
               for gp in range(model.num_quad_points[eid] * 2)}

    eps_bar_p_n = {(eid, gp): 0 for eid in model.elements.keys()
                   for gp in range(model.num_quad_points[eid] * 2)}

    # initialize dict to store incremental plastic multiplier
    # used to compute the consistent tangent matrix
    dgamma_n = {(eid, gp): 0 for eid in model.elements.keys()
                for gp in range(model.num_quad_points[eid] * 2)}

    # external load vector
    # Only traction for now
    # TODO: external_load_vector function DONE for traction only
    f_ext_bar = external_load_vector(model)

    # Loop over load increments
    for incr_id, lmbda in enumerate(load_increment):
        print('--------------------------------------')
        print(f'Load increment {lmbda:.2f}:')
        print('--------------------------------------')
        f_ext = lmbda * f_ext_bar  # load vector for this pseudo time step

        # Initial parameters for N-R
        # Initial displacement increment for all dof
        du = np.zeros(num_dof)

        # Begin global Newton-Raphson
        for k in range(0, max_num_iter):
            # (ii) & (iii) Tangent stiffness matrix and residual
            # k = 0 -> du = 0
            # build internal load vector and consistent tangent matrix
            f_int, K_T, int_var = local_solver(model, num_dof, du,
                                               eps_e_n,
                                               eps_bar_p_n,
                                               dgamma_n,
                                               max_num_local_iter)
            # compute global residual vector
            r = f_int - f_ext

            # apply boundary condition for displacement control case
            if model.imposed_displ is not None:
                # Make a copy of the imposed displacement
                imposed_displ = dict(model.imposed_displ)
                for line, (d1, d2) in imposed_displ.items():
                    if d1 is not None:
                        d1 *= lmbda
                    if d2 is not None:
                        d2 *= lmbda
                    # update dictionary with this load factor
                    imposed_displ[line] = (d1, d2)
                # update model displacement bc in order to enforce this
                # load step displacement
                model.displacement_bc.update(imposed_displ)

            # apply boundary conditions modify mtrix and vectors
            K_T_m, r_m = dirichlet(K_T, r, model)
            # compute the N-R correction (delta u)
            nr_correction = - np.linalg.solve(K_T_m, r_m)
            # displacement increment on the NR k loop, du starts at 0
            # for each load step
            du += nr_correction
            # update displacement with increment
            u += nr_correction

            # check convergence
            err = np.linalg.norm(r)
            energy_norm = du.T @ r
            print(f'Iteration {k + 1} error {err:.1e} '
                  f'energy norm {energy_norm:.1e}')
            if err <= tol:
                # solution converged +1 because it started in 0
                print(f'Converged with {k + 1} iterations error {err:.1e} '
                      f'Energy norm {energy_norm:.1e}')

                # TODO: store variable in an array DONE
                displ[:, incr_id] = u

                # TODO: update interal variables converged DONE
                # update elastic strain for this element for this gp
                eps_e_n = int_var['eps_e']
                # update cummulative plastic strain
                eps_bar_p_n = int_var['eps_bar_p']
                # update incremental plastic multiplier
                dgamma_n = int_var['dgamma']

                # TODO: save internal variables to a file DONE
                displ_dic = dof2node(u, model)
                write_field(displ_dic, model.mesh.name,
                            'Displacement', 2, lmbda, incr_id, start)

                # element average of cummulative plastic strain
                eps_bar_p_avg = {eid: eps_bar_p_n[(eid, gp)]
                                 for eid in model.elements.keys()
                                 for gp in range(4)}
                write_field(eps_bar_p_avg, model.mesh.name,
                            'Cummulative plastic strain', 1,
                            lmbda, incr_id, start, datatype='Element')

                # sig_ele {eid: [sig_x, sig_y, sig_xy]}
                sig_ele = int_var['sig_ele']
                sig_x = {eid: sig_ele[eid][0] for eid in model.elements.keys()}
                write_field(sig_x, model.mesh.name, 'Sigma x', 1,
                            lmbda, incr_id, start, datatype='Element')

                break
            else:
                # did't converge, continue to next global iteration
                continue
        else:
            raise Exception(f'Solution did not converge at time step '
                            f'{incr_id + 1} after {k} iterations with error '
                            f'{err:.1e}')
    end = time.time()
    print(f'Solution finished in {end - start:.3f}s')
    return displ, load_increment


def local_solver(model, num_dof, du, eps_e_n, eps_bar_p_n, dgamma_n,
                 max_num_local_iter):
    """Assemble internal load vector for each N-R iteration

    Parameters
    ----------
    model : Model object
    num_dof : number of degree's of freedom
    du : displacement increment
    eps_e_n : dict {(eid, gp_id): ndarray shape (3)}
        Stores the elastic strain at previous step for each element and each
        gauss point. This value is updated every time this function is called
    eps_bar_p_n : dict {(eid, gp_id): float}
        Stores the accumulated plastic strain at previous step for each element
        and each gauss point (gp). This value is updated every time this
        function is called
    dgamma_n : dict {(eid, gp_id): float}

    Returns
    -------
    f_int : ndarray shape (num_dof)
    K_T : ndarray shape (num_dof, num_dof)
    ep_flag : str
    int_var : dict
        dictionary of interal state variables for each gauss point for
        each element

    Note
    ----
    Reference Eq. 4.65 (1) Neto 2008

    Find the stress for a fiven displacement u, then multiply the stress for
    the strain-displacement matrix trasnpose and integrate it over domain.

    Procedure:
    1. Loop over elements
    2. Loop over each gauss point
        2.1 Compute strain increment from displacement increment
        2.2 Compute elastic trial strain
        2.3 Update state variables (stress, elastic strain, plastic multiplier,
                                    accumulated plastic strain)
        2.4 Compute internal element force vector
        2.5 Compute element tangent stiffness matrix
    3. Assemble global internal force vector and tangent stiffness matrix

    """
    # initialize global vector and matrices
    f_int = np.zeros(num_dof)
    K_T = np.zeros((num_dof, num_dof))

    # dictionary with local variables
    # new every local N-R iteration
    # use to save converged value
    int_var = {'eps_e': {}, 'eps_bar_p': {}, 'sig_ele': {}, 'dgamma': {}}

    # Loop over elements
    for eid, [etype, *edata] in model.elements.items():
        # create element object
        element = constructor(eid, etype, model)
        # recover element nodal displacement increment,  shape (8,)
        dof = np.array(element.dof) - 1  # numpy starts at 0
        du_ele = du[dof]

        # material properties
        E, nu = element.E, element.nu
        # Hardening modulus and yield stress
        # TODO: include this as a parameter of the material later DONE
        try:
            H = model.material.H[element.physical_surf]
            sig_y0 = model.material.sig_y0[element.physical_surf]
        except (AttributeError, KeyError) as err:
            raise Exception('Missing material property H and sig_y0 in'
                            'the material object')

        # initialize array for element internal force vector
        f_int_e = np.zeros(8)
        # initialize array for element consistent tangent matrix
        k_T_e = np.zeros((8, 8))

        # initialize stress array to compute average
        int_var['sig_ele'][eid] = np.zeros(3)

        # loop over quadrature points
        for gp_id, [w, gp] in enumerate(zip(element.gauss.weights,
                                            element.gauss.points)):
            # build element strain-displacement matrix shape (3, 8)
            N, dN_ei = element.shape_function(xez=gp)
            dJ, dN_xi, _ = element.jacobian(element.xyz, dN_ei)
            B = element.gradient_operator(dN_xi)

            # compute strain increment from
            # current displacement increment, shape (3, )
            deps = B @ du_ele

            # elastic trial strain
            # use the previous value stored for this element and this gp
            eps_e_trial = eps_e_n[(eid, gp_id)] + deps

            # trial accumulated plastic strain
            # this is only updated when converged
            eps_bar_p_trial = eps_bar_p_n[(eid, gp_id)]

            # update internal variables for this gauss point
            sig, eps_e, eps_bar_p, dgamma, ep_flag = state_update_mises(
                E, nu, H, sig_y0, eps_e_trial, eps_bar_p_trial,
                max_num_local_iter)

            # print(f'gp {gp_id} eps_bar_p {eps_bar_p:.1e} dgamma {dgamma:.1e}'
            #       f'plastic? {ep_flag}')
            # TODO Only update when converged! outside this function! DONE
            # save solution of constitutive equation -> internal variables
            # int_var is a dictionary with the internal variables
            # each interal variable is a dictionary with a tuple key
            # the tuple (eid, gp_id) for each element and each gauss point
            int_var['eps_e'][(eid, gp_id)] = eps_e
            int_var['eps_bar_p'][(eid, gp_id)] = eps_bar_p
            int_var['dgamma'][(eid, gp_id)] = dgamma

            # average of gauss point stress for element stress
            int_var['sig_ele'][eid] += sig / len(element.gauss.weights)

            # compute element internal force (gaussian quadrature)
            f_int_e += B.T @ sig * (dJ * w * element.thickness)

            # TODO: material properties from element, E, nu, H DONE
            # TODO: ep_flag comes from the state update? DONE
            # use dgama from previous global iteration
            D = consistent_tangent_mises(
                dgamma_n[(eid, gp_id)], sig, E, nu, H, ep_flag)

            # element consistent tanget matrix (gaussian quadrature)
            k_T_e += B.T @ D @ B * (dJ * w * element.thickness)

        # Build global matrices outside the quadrature loop
        # += because elements can share same dof
        f_int[element.id_v] += f_int_e
        K_T[element.id_m] += k_T_e

    return f_int, K_T, int_var


def external_load_vector(model):
    """Assemble external load vector

    Note
    ----
    Reference Eq. 4.68 Neto 2008

    """
    # TODO: add body force later
    # only traction vector for now
    Pt = neumann(model)
    return Pt


def get_free_dof(model):
    """Get the free dof list
    
    Ignore supports for now

    """
    restrained_dof = []
    for d_location, d_vector in model.imposed_displ.items():
        physical_element = model.get_physical_element(d_location)
        for eid, [etype, *edata] in physical_element.items():
            restrained_dof.extend(model.nodes_dof[eid])
    all_dof = []
    for nid, dof in model.nodes_dof.items():
        all_dof.extend(dof)
    print(all_dof)
    free_dof = list(set(all_dof) - set(restrained_dof))
    return free_dof


if __name__ == '__main__':
    pass
