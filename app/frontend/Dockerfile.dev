FROM node:20-alpine

WORKDIR /app

# Install deps first to leverage Docker cache
COPY package.json package-lock.json ./
RUN npm ci

# Copy app source
COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0", "-p", "3000"]