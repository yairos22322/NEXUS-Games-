#version 150

uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform float u_time;
uniform float u_seed;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 v_uv;
out vec3 v_world;
out vec3 v_normal;
out float v_wave;

float waveHeight(vec2 p) {
    float w1 = sin(p.x * 0.72 + u_time * 1.45 + u_seed * 7.0);
    float w2 = cos(p.y * 0.56 - u_time * 1.18 + u_seed * 11.0);
    float w3 = sin((p.x + p.y) * 0.31 + u_time * 0.84);
    float w4 = sin((p.x * 0.27 - p.y * 0.41) + u_time * 0.63 + u_seed * 3.0);
    return w1 * 0.020 + w2 * 0.017 + w3 * 0.013 + w4 * 0.010;
}

void main() {
    vec4 position = p3d_Vertex;
    float wave = waveHeight(position.xy);
    position.z += wave;

    float eps = 0.08;
    float hx = waveHeight(position.xy + vec2(eps, 0.0)) - waveHeight(position.xy - vec2(eps, 0.0));
    float hy = waveHeight(position.xy + vec2(0.0, eps)) - waveHeight(position.xy - vec2(0.0, eps));
    vec3 localNormal = normalize(vec3(-hx / (2.0 * eps), -hy / (2.0 * eps), 1.0));

    vec4 world = p3d_ModelMatrix * position;
    vec3 worldNormal = normalize(mat3(p3d_ModelMatrix) * localNormal);

    v_uv = p3d_MultiTexCoord0;
    v_world = world.xyz;
    v_normal = worldNormal;
    v_wave = wave;
    gl_Position = p3d_ModelViewProjectionMatrix * position;
}
