<?php

declare(strict_types=1);

final class HomeController
{
    public function __invoke(): string
    {
        return 'home';
    }
}
