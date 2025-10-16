import argparse
import logging
import os
import numpy as np
import rerun as rr
from scipy.spatial.transform import Rotation as R

logger = logging.getLogger("api.adjust_pose.manipulator")

def decompose_pose(pose: np.ndarray):
    """
    Decompose a 4x4 transformation matrix
    into translation and quaternion (xyzw) for Rerun.

    Parameters:
        pose (np.ndarray): A 4x4 transformation matrix.

    Returns:
        translation (list): Translation vector [x, y, z].
        quaternion (rr.Quaternion): Quaternion rotation in (xyzw) order.
    """
    assert pose.shape == (4, 4), 'lidar2ego must be a 4x4 matrix'

    # Extract translation vector
    translation = pose[:3, 3].tolist()

    # Extract rotation matrix
    rotation_matrix = pose[:3, :3]

    # Convert to quaternion (scipy returns in (x, y, z, w) order)
    quat_xyzw = R.from_matrix(rotation_matrix).as_quat()

    # Convert to rr.Quaternion
    quaternion = rr.Quaternion(xyzw=quat_xyzw.tolist())

    return translation, quaternion


def compose_pose(trans, rot_quat=None, rot_euler=None):
    if rot_quat is not None:
        rot_mat = R.from_quat(rot_quat).as_matrix()
    elif rot_euler is not None:
        rot_mat = R.from_euler(
            'xyz', rot_euler, degrees=True).as_matrix()

    pose = np.eye(4)
    pose[:3, :3] = rot_mat
    pose[:3, -1] = trans

    return pose


def manipulate_pose(args):
    base_rrd = args.base_rrd
    base_rrd_fname = os.path.basename(base_rrd)
    rid = base_rrd_fname[:base_rrd_fname.index('_LMGI_')]
    logger.info("Manipulating pose for %s (recording_id=%s)", base_rrd, rid)

    rr.init('add_anns_to_base_rrd', recording_id=rid)
    rr.log_file_from_path(base_rrd)

    recording = rr.dataframe.load_recording(base_rrd)
    logger.info("Recording object loaded: %s", recording)
    view = recording.view(index='timestamp', contents='world/odom_lidar')
    view_table = view.select_static()
    transform_df = view_table.read_pandas()

    rot_quat = transform_df.iloc[0]['/world/odom_lidar:RotationQuat'][0]
    trans = transform_df.iloc[0]['/world/odom_lidar:Translation3D'][0]
    logger.info("Original translation=%s rotation_quat=%s", trans, rot_quat)

    pose_ori = compose_pose(trans, rot_quat=rot_quat)

    mainp_trans = np.array(args.xyz, np.float32)
    mainp_euler = np.array(args.rpy, np.float32)
    pose_manipulate = compose_pose(mainp_trans, rot_euler=mainp_euler)
    pose_new = pose_ori @ pose_manipulate
    odom2world_trans, odom2world_rot_quat = decompose_pose(pose_new)
    logger.info("Applied offsets translation=%s rotation_euler=%s", mainp_trans.tolist(), mainp_euler.tolist())
    logger.info("New translation=%s rotation_quat=%s", odom2world_trans, odom2world_rot_quat)
    rr.set_time_seconds('timestamp', 0)
    rr.log(f'world/odom_lidar',
           rr.Transform3D(
               translation=odom2world_trans,
               rotation=odom2world_rot_quat,
               from_parent=False),
           static=True)
    
    out_rrd = base_rrd.replace('_PRIOR.rrd', '.rrd')
    
    rr.save(out_rrd)
    logger.info("Saved manipulated recording to %s", out_rrd)

def comma_separated_list(arg):
    return [float(x) for x in arg.split(',')]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Add annotations to base rrd')
    parser.add_argument('base_rrd', type=str, help='scene base rrd file path')
    parser.add_argument('--xyz', type=comma_separated_list, help='Translation(m)',
                        default=[0, 0, 0])
    parser.add_argument('--rpy', type=comma_separated_list, help='Rotation(degrees)',
                        default=[0, 0, 0])
    args = parser.parse_args()
    manipulate_pose(args)
