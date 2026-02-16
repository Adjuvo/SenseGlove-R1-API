// quick compile (copy to lib folder after) : 
// g++ -shared -o libSG_math.dll -fPIC SG_math.cpp
// g++ -shared -o libSG_math.so -fPIC SG_math.cpp

// #ifdef _WIN32
// #define EXPORT __declspec(dllexport)
// #else
// #define EXPORT
// #endif


#include <sstream>
#include <iostream>
#include <vector>
#include <cmath>
#include <array>

extern "C" {
    struct Quaternion {
        double w, x, y, z;
    };

    struct Vec3 {
        double x, y, z;
    };
    

        
    // std::string quat_to_string(const Quaternion& q) {
    //     std::ostringstream oss;
    //     oss << "Quaternion(w: " << q.w << ", x: " << q.x << ", y: " << q.y << ", z: " << q.z << ")";
    //     return oss.str();
    // }
    
    // // Function to convert Vec3 to string
    // std::string vec_to_string(const Vec3& v) {
    //     std::ostringstream oss;
    //     oss << "Vec3(x: " << v.x << ", y: " << v.y << ", z: " << v.z << ")";
    //     return oss.str();
    // }


    Quaternion quaternion_from_euler(double ax, double ay, double az) {
        double cx = cos(ax / 2), cy = cos(ay / 2), cz = cos(az / 2);
        double sx = sin(ax / 2), sy = sin(ay / 2), sz = sin(az / 2);
        return {cz * cy * cx + sz * sy * sx,
                cz * cy * sx - sz * sy * cx,
                cz * sy * cx + sz * cy * sx,
                sz * cy * cx - cz * sy * sx};
    }

    Quaternion quaternion_multiply(Quaternion q1, Quaternion q2) {
        return {
            q1.w * q2.w - q1.x * q2.x - q1.y * q2.y - q1.z * q2.z,
            q1.w * q2.x + q1.x * q2.w + q1.y * q2.z - q1.z * q2.y,
            q1.w * q2.y - q1.x * q2.z + q1.y * q2.w + q1.z * q2.x,
            q1.w * q2.z + q1.x * q2.y - q1.y * q2.x + q1.z * q2.w
        };
    }

    Vec3 quaternion_rotate(Quaternion q, Vec3 v) {
        Quaternion q_v = {0, v.x, v.y, v.z};
        Quaternion q_conj = {q.w, -q.x, -q.y, -q.z};
        Quaternion rotated = quaternion_multiply(quaternion_multiply(q, q_v), q_conj);
        return {rotated.x, rotated.y, rotated.z};
    }

    void set_quat_to_array(double* quaternions, int index, Quaternion quat)
    {
        int i = index;
        quaternions[i * 4] = quat.w;
        quaternions[i * 4 + 1] = quat.x;
        quaternions[i * 4 + 2] = quat.y;
        quaternions[i * 4 + 3] = quat.z;
    }

    void set_vec_to_array(double* positions, int index, Vec3 pos)
    {
        int i = index;
        //std::cout << "indexpos " << i*3 << std::endl;
        positions[i * 3] = pos.x;
        //std::cout << "posX " << pos.x << std::endl;
        positions[i * 3 + 1] = pos.y;
        positions[i * 3 + 2] = pos.z;

    }
    

    void forward_kinematics_3d(double* base, double* base_quat, double* linkages, double* angles, int num_joints, double* positions, double* quaternions) {
        Quaternion current_rotation = {base_quat[0], base_quat[1], base_quat[2], base_quat[3]}; // Identity quaternion
        Vec3 current_position = {base[0], base[1], base[2]};
        
        //std::cout << "base " << vec_to_string(current_position) << std::endl;

        set_vec_to_array(positions, 0, current_position);
        set_quat_to_array(quaternions, 0, current_rotation);

        for (int i = 0; i < num_joints; i++) {
            double ax = angles[i * 3], ay = angles[i * 3 + 1], az = angles[i * 3 + 2];
            Quaternion delta_rotation = quaternion_from_euler(ax, ay, az);
            current_rotation = quaternion_multiply(current_rotation, delta_rotation);
            

            //std::cout << "result" << quat_to_string(current_rotation) << std::endl;
            
            //std::cout << "linkages " << linkages[i * 3] << ", " <<  linkages[i * 3 + 1] << "," << linkages[i * 3 + 2] << std::endl;
            Vec3 direction = quaternion_rotate(current_rotation, {linkages[i * 3], linkages[i * 3 + 1], linkages[i * 3 + 2]});
            //std::cout << "dir" <<  vec_to_string(direction) << std::endl;
            
            //std::cout << "newpos" << vec_to_string(direction) << std::endl;
            current_position = {current_position.x + direction.x, current_position.y + direction.y, current_position.z + direction.z};
            
            set_vec_to_array(positions, i + 1, current_position);
            set_quat_to_array(quaternions, i + 1, current_rotation);
            
            
           //     std::cout << "pos" << i << std::endl;
           // for (int j = 0; j < (num_joints+1)*3;j++)
            //std::cout << positions[j] << ", ";
        }
    }
}


// int main() {
//     // double base[3] = {1, 2, 3};
//     // double linkages[8*3] = {1,0,0,2,0,0,3,0,0,4,0,0,5,0,0,6,0,0,7,0,0,8,0,0};
//     // double angles[8*3] = {0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};
    
//     int nrLinkages = 3;
    
//     double base[3] = {3, 3, 3};
//     double linkages[nrLinkages*3] = {1,0,0,2,0,0,3,0,0};
//     double angles[nrLinkages*3] = {0,0,0,0,0,0,0,0,0};
//     // Write C++ code here
//     double positions[(nrLinkages + 1)*3] = {-1};  // Initialize all values to zero
//     double rotations[(nrLinkages + 1)*4] = {-1};
    
//     std::fill(positions, positions + (nrLinkages + 1) * 3, -1);
//     std::fill(rotations, rotations + (nrLinkages + 1) * 4, -1);
//     forward_kinematics_3d(base, linkages, angles, nrLinkages, positions, rotations);
    

        

//     return 0;
// }
//}