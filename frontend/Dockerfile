# Use a lightweight Nginx image
FROM nginx:alpine

# Remove default nginx landing page
RUN rm -rf /usr/share/nginx/html/*

# Copy your custom frontend files into the container
COPY index.html /usr/share/nginx/html/index.html

