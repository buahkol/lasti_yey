-- Database terpisah untuk pytest (tes menghapus schema public, jadi jangan pernah memakai `simonpro`).
-- Dijalankan otomatis oleh docker compose saat volume pertama kali dibuat. Untuk volume yang sudah
-- ada:  docker compose exec postgres psql -U postgres -c "CREATE DATABASE simonpro_test;"
CREATE DATABASE simonpro_test;
