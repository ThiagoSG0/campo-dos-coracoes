#version 400 core
layout(location = 0) in vec4 vPosition;
layout(location = 1) in vec4 vColors;
uniform vec2 u_canvas;
uniform vec2 u_position;
uniform vec2 u_scale;
uniform float u_angle;
uniform vec4 u_color;
uniform float u_rainbow;
out vec4 v2fcolor;
void main() {
    float c = cos(u_angle), s = sin(u_angle);
    vec2 p = vPosition.xy * u_scale;
    p = mat2(c, s, -s, c) * p + u_position;
    gl_Position = vec4(2.0 * p / u_canvas - 1.0, 0.0, 1.0);
    v2fcolor = vec4(mix(u_color.rgb, vColors.rgb, u_rainbow), u_color.a);
}
