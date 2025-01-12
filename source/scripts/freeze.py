#!/usr/bin/env python3

# freeze.py :
# see https://blog.metaflow.fr/tensorflow-how-to-freeze-a-model-and-serve-it-with-a-python-api-d4f3596b3adc

import platform
import os, argparse, json
import sys

from deepmd.env import tf

dir = os.path.dirname(os.path.realpath(__file__))

from tensorflow.python.framework import ops

# load force module
if platform.system() == "Windows":
    ext = "dll"
elif platform.system() == "Darwin":
    ext = "dylib"
else:
    ext = "so"
module_path = os.path.dirname(os.path.realpath(__file__)) + "/../"
assert (os.path.isfile (module_path  + "deepmd/libop_abi.{}".format(ext) )), "force module does not exist"
op_module = tf.load_op_library(module_path + "deepmd/libop_abi.{}".format(ext))

# load grad of force module
sys.path.append (module_path )
import deepmd._prod_force_grad
import deepmd._prod_virial_grad
import deepmd._prod_force_se_a_grad
import deepmd._prod_virial_se_a_grad
import deepmd._prod_force_se_r_grad
import deepmd._prod_virial_se_r_grad
import deepmd._soft_min_force_grad
import deepmd._soft_min_virial_grad

def _make_node_names(model_type = None) : 
    if model_type == 'ener':
        nodes = "o_energy,o_force,o_virial,o_atom_energy,o_atom_virial,descrpt_attr/rcut,descrpt_attr/ntypes,fitting_attr/dfparam,fitting_attr/daparam,model_attr/tmap,model_attr/model_type"
    elif model_type == 'wfc':
        nodes = "o_wfc,descrpt_attr/rcut,descrpt_attr/ntypes,model_attr/tmap,model_attr/sel_type,model_attr/model_type"
    elif model_type == 'dipole':
        nodes = "o_dipole,descrpt_attr/rcut,descrpt_attr/ntypes,model_attr/tmap,model_attr/sel_type,model_attr/model_type"
    elif model_type == 'polar':
        nodes = "o_polar,descrpt_attr/rcut,descrpt_attr/ntypes,model_attr/tmap,model_attr/sel_type,model_attr/model_type"
    else:
        raise RuntimeError('unknow model type ' + model_type)
    return nodes

def freeze_graph(model_folder, 
                 output, 
                 output_node_names = None):
    # We retrieve our checkpoint fullpath
    checkpoint = tf.train.get_checkpoint_state(model_folder)
    input_checkpoint = checkpoint.model_checkpoint_path
    
    # We precise the file fullname of our freezed graph
    absolute_model_folder = "/".join(input_checkpoint.split('/')[:-1])
    output_graph = absolute_model_folder + "/" + output

    # Before exporting our graph, we need to precise what is our output node
    # This is how TF decides what part of the Graph he has to keep and what part it can dump
    # NOTE: this variable is plural, because you can have multiple output nodes
    # output_node_names = "energy_test,force_test,virial_test,t_rcut"

    # We clear devices to allow TensorFlow to control on which device it will load operations
    clear_devices = True
    
    # We import the meta graph and retrieve a Saver
    saver = tf.train.import_meta_graph(input_checkpoint + '.meta', clear_devices=clear_devices)

    # We retrieve the protobuf graph definition
    graph = tf.get_default_graph()
    input_graph_def = graph.as_graph_def()

    # We start a session and restore the graph weights
    with tf.Session() as sess:
        saver.restore(sess, input_checkpoint)
        model_type = sess.run('model_attr/model_type:0', feed_dict = {}).decode('utf-8')
        if output_node_names is None :
            output_node_names = _make_node_names(model_type)
        print('The following nodes will be frozen: %s' % output_node_names)

        # We use a built-in TF helper to export variables to constants
        output_graph_def = tf.graph_util.convert_variables_to_constants(
            sess, # The session is used to retrieve the weights
            input_graph_def, # The graph_def is used to retrieve the nodes 
            output_node_names.split(",") # The output node names are used to select the usefull nodes
        ) 

        # Finally we serialize and dump the output graph to the filesystem
        with tf.gfile.GFile(output_graph, "wb") as f:
            f.write(output_graph_def.SerializeToString())
        print("%d ops in the final graph." % len(output_graph_def.node))


def freeze (args):
    freeze_graph(args.folder, args.output, args.nodes)

