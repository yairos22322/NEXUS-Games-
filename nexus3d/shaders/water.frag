#version 150

uniform vec4 u_water_color;
uniform vec4 u_camera_pos;
uniform float u_time;
uniform float u_seed;
uniform float u_reflection_strength;
in vec2 v_uv;
in vec3 v_world;
in vec3 v_normal;
in float v_wave;
out vec4 p3d_FragColor;

float hash21(vec2 p) {
    p = fract(p * vec2(443.897, 441.423));
    p += dot(p, p + 19.19);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void main() {
    vec3 normal = normalize(v_normal);
    vec3 viewDir = normalize(u_camera_pos.xyz - v_world);

    vec2 flowA = v_uv * 12.0 + vec2(u_time * 0.045, -u_time * 0.026);
    vec2 flowB = v_uv.yx * 18.0 + vec2(-u_time * 0.031, u_time * 0.021);
    float microA = noise(flowA * 2.0 + u_seed * 11.0);
    float microB = noise(flowB * 2.7 + u_seed * 7.0);
    float micro = microA * 0.58 + microB * 0.42;

    normal = normalize(normal + vec3((microA - 0.5) * 0.12, (microB - 0.5) * 0.12, 0.0));

    float ndv = clamp(dot(normal, viewDir), 0.0, 1.0);
    float fresnel = 0.035 + 0.965 * pow(1.0 - ndv, 5.0);

    vec3 deepColor = u_water_color.rgb * 0.45;
    vec3 shallowColor = u_water_color.rgb * 1.20 + vec3(0.015, 0.035, 0.055);
    float waveLighting = clamp(0.48 + normal.z * 0.45 + v_wave * 5.0, 0.0, 1.0);
    vec3 water = mix(deepColor, shallowColor, waveLighting);

    // Procedural sky approximation for the reflection term. This is cheaper
    // than a full reflection camera and still reacts convincingly to view angle.
    vec3 horizonReflection = vec3(0.16, 0.24, 0.34);
    vec3 zenithReflection = vec3(0.035, 0.075, 0.13);
    float reflectedUp = clamp(reflect(-viewDir, normal).z * 0.5 + 0.5, 0.0, 1.0);
    vec3 reflection = mix(horizonReflection, zenithReflection, reflectedUp);
    reflection *= 0.78 + micro * 0.35;

    vec3 lightDir = normalize(vec3(-0.36, 0.48, 0.80));
    vec3 halfDir = normalize(lightDir + viewDir);
    float specular = pow(max(dot(normal, halfDir), 0.0), 110.0);
    specular *= 0.38 + fresnel * 1.35;

    float sparkle = pow(max(micro - 0.63, 0.0) * 2.7, 7.0) * fresnel;
    vec3 finalColor = mix(water, reflection, fresnel * 0.72 * u_reflection_strength);
    finalColor += vec3(0.78, 0.90, 1.0) * (specular * 0.68 + sparkle * 0.22);

    float edge = smoothstep(0.0, 0.10, v_uv.x) * smoothstep(0.0, 0.10, v_uv.y)
               * smoothstep(0.0, 0.10, 1.0 - v_uv.x) * smoothstep(0.0, 0.10, 1.0 - v_uv.y);
    float alpha = mix(0.30, 0.63, fresnel) * edge;
    p3d_FragColor = vec4(finalColor, alpha);
}
