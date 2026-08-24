#version 150

uniform mat4 p3d_ModelViewProjectionMatrix;
uniform float u_time;
uniform float u_seed;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 v_uv;
out vec3 v_local;
out float v_wave;

void main() {
    vec4 position = p3d_Vertex;
    float w1 = sin(position.x * 0.72 + u_time * 1.45 + u_seed * 7.0);
    float w2 = cos(position.y * 0.56 - u_time * 1.18 + u_seed * 11.0);
    float w3 = sin((position.x + position.y) * 0.31 + u_time * 0.84);
    float wave = w1 * 0.012 + w2 * 0.010 + w3 * 0.008;
    position.z += wave;
    v_uv = p3d_MultiTexCoord0;
    v_local = position.xyz;
    v_wave = wave;
    gl_Position = p3d_ModelViewProjectionMatrix * position;
}
