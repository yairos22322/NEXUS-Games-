#version 150

uniform vec4 u_water_color;
uniform vec4 u_camera_pos;
uniform float u_time;
uniform float u_seed;
in vec2 v_uv;
in vec3 v_local;
in float v_wave;
out vec4 p3d_FragColor;

float hash21(vec2 p) {
    p = fract(p * vec2(443.897, 441.423));
    p += dot(p, p + 19.19);
    return fract(p.x * p.y);
}

void main() {
    vec2 uv = v_uv * 7.0;
    float rippleA = sin(uv.x * 2.1 + u_time * 2.4 + sin(uv.y));
    float rippleB = cos(uv.y * 2.7 - u_time * 1.9 + cos(uv.x));
    float ripple = rippleA * rippleB * 0.5 + 0.5;
    vec3 water = u_water_color.rgb;
    vec3 bright = water * 1.85 + vec3(0.07, 0.11, 0.16);
    float glint = pow(max(0.0, ripple), 9.0) * 0.42;
    float edge = smoothstep(0.0, 0.14, v_uv.x) * smoothstep(0.0, 0.14, v_uv.y)
               * smoothstep(0.0, 0.14, 1.0 - v_uv.x) * smoothstep(0.0, 0.14, 1.0 - v_uv.y);
    vec3 finalColor = mix(water * 0.66, bright, glint);
    finalColor += vec3(0.01, 0.015, 0.025) * (sin(u_time + v_local.x * 0.3) * 0.5 + 0.5);
    float alpha = (0.24 + glint * 0.22) * edge;
    p3d_FragColor = vec4(finalColor, alpha);
}
